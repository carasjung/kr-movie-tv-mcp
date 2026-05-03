"""
pipeline/jobs/sync_mydramalist.py — Sync Korean drama data from MyDramaList.

Enriches tv_shows with:
- MDL ratings and vote counts
- Community tags (unique to MDL)
- Airing status (most up-to-date source)
- Native Korean titles
- Watch provider links

Schedule: Nightly at 3am
"""

import time
from prefect import flow, task, get_run_logger

from data_sources.mydramalist import (
    get_airing_dramas,
    get_popular_dramas,
    get_top_dramas,
    get_upcoming_dramas,
    get_drama_details,
)
from db.queries import (
    upsert_show,
    get_show_by_tmdb_id,
    _supabase,
)
from pipeline.utils import (
    get_logger,
    parse_date,
    normalize_genres,
    normalize_tags,
    safe_float,
    safe_int,
    map_mdl_status,
    extract_mdl_show_id,
    polite_delay,
    run_with_retry,
    batch,
)

log = get_logger("sync_mdl")


def _transform_show(card: dict, details: dict = None) -> dict:
    """Transform MDL show card + details into DB schema."""
    data = {
        "mdl_id":          str(card["mdl_id"]) if card.get("mdl_id") else None,
        "mdl_slug":        card.get("slug"),
        "title_english":   card.get("title"),
        "mdl_rating":      safe_float(card.get("rating")),
        "total_episodes":  safe_int(card.get("episode_count")),
        "year":            safe_int(card.get("year")),
        "content_type":    card.get("content_type", "Korean Drama"),
        "poster_url":      card.get("poster_url"),
    }

    if details:
        raw_details = details.get("details", {})
        data.update({
            "title_korean":    details.get("native_title"),
            "synopsis_short":  details.get("synopsis"),
            "genres":          normalize_genres(details.get("genres", [])),
            "tags":            normalize_tags(details.get("tags", [])),
            "network":         raw_details.get("original_network"),
            "first_air_date":  parse_date(raw_details.get("aired", "").split("-")[0].strip()) if raw_details.get("aired") else None,
            "last_air_date":   parse_date(raw_details.get("aired", "").split("-")[-1].strip()) if raw_details.get("aired") else None
        })

        # Status from details
        airing_status = raw_details.get("status")
        if airing_status:
            data["status"] = map_mdl_status(airing_status)
        elif card.get("content_type", "").lower() == "upcoming":
            data["status"] = "Upcoming"

        # Votes
        if details.get("votes"):
            data["mdl_votes"] = safe_int(details["votes"])

    return {k: v for k, v in data.items() if v is not None}


@task(retries=2, retry_delay_seconds=10)
def fetch_all_mdl_shows() -> list[dict]:
    """Fetch all MDL show cards across all lists."""
    log.info("Fetching MDL show lists...")
    all_shows = {}

    for fetch_fn, label in [
        (get_airing_dramas, "airing"),
        (get_upcoming_dramas, "upcoming"),
        (get_popular_dramas, "popular"),
        (get_top_dramas, "top"),
    ]:
        shows = run_with_retry(fetch_fn, max_pages=5)
        if shows:
            for show in shows:
                if show.get("mdl_id"):
                    all_shows[show["mdl_id"]] = show
            log.info(f"  {label}: {len(shows)} shows")
        polite_delay(2.0)

    log.info(f"Total unique MDL shows: {len(all_shows)}")
    return list(all_shows.values())


@task(retries=2, retry_delay_seconds=10)
def sync_mdl_show(card: dict) -> dict | None:
    """Fetch details for one MDL show and upsert to DB."""
    slug = card.get("slug")
    if not slug:
        return None

    details = run_with_retry(get_drama_details, slug)
    if not details:
        return None

    show_data = _transform_show(card, details)

    # Try to find existing show by MDL ID to get the tmdb_id
    if show_data.get("mdl_id"):
        existing = _supabase.table("tv_shows") \
            .select("id, tmdb_id") \
            .eq("mdl_id", show_data["mdl_id"]) \
            .execute().data
        if existing:
            # Update existing record
            result = _supabase.table("tv_shows") \
                .update(show_data) \
                .eq("id", existing[0]["id"]) \
                .execute()
            return result.data[0] if result.data else None

    # Insert new record (no TMDB match yet — TMDB job will link later)
    if show_data.get("title_english"):
        return upsert_show(show_data)

    return None


@flow(name="sync_mydramalist", log_prints=True)
def sync_mdl_flow(limit: int = None):
    """
    Main MDL sync flow.

    Args:
        limit: Max shows to process (None = all)
    """
    logger = get_run_logger()

    shows = fetch_all_mdl_shows()
    if limit:
        shows = shows[:limit]

    logger.info(f"Syncing {len(shows)} MDL shows...")

    synced = 0
    failed = 0
    for show in shows:
        result = sync_mdl_show(show)
        if result:
            synced += 1
        else:
            failed += 1
        polite_delay(1.5)  # MDL needs polite delays

    logger.info(f"MDL sync complete: {synced} synced, {failed} failed")


if __name__ == "__main__":
    sync_mdl_flow(limit=5)