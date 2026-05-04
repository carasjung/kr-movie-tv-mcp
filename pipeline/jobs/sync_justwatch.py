"""
pipeline/jobs/sync_justwatch.py — Sync streaming availability from JustWatch.

Enriches the streaming_availability table with where-to-watch data
across multiple regions for all Korean movies and TV shows.

Regions covered: US, UK, CA, AU (international English-speaking markets)

Schedule: Weekly on Wednesday at 3am
"""

from prefect import flow, task, get_run_logger

from data_sources.justwatch import (
    get_streaming_availability,
    title_to_slug,
)
from db.queries import (
    upsert_streaming_bulk,
    _supabase,
)
from pipeline.utils import (
    get_logger,
    polite_delay,
    run_with_retry,
    batch,
)

log = get_logger("sync_justwatch")

REGIONS = ["us", "uk", "ca", "au"]


def _get_all_titles() -> dict:
    """Get all movies and shows from DB with their JustWatch slugs."""
    movies = _supabase.table("movies") \
        .select("id, title_english, justwatch_slug, release_year") \
        .execute().data or []

    shows = _supabase.table("tv_shows") \
        .select("id, title_english, justwatch_slug, year") \
        .execute().data or []

    return {"movies": movies, "shows": shows}


def _transform_offers(offers: list[dict], movie_id: str | None = None, show_id: str | None = None) -> list[dict]:
    """Transform JustWatch streaming offers into DB schema rows."""
    rows = []
    for offer in offers:
        if not offer.get("provider"):
            continue
        rows.append({
            "movie_id":          movie_id,
            "show_id":           show_id,
            "region":            offer.get("region"),
            "provider":          offer.get("provider"),
            "monetization_type": offer.get("monetization_type"),
            "quality":           offer.get("quality"),
            "price":             offer.get("price"),
            "watch_url":         offer.get("watch_url"),
            "provider_logo_url": offer.get("provider_logo"),
        })
    return rows


@task(retries=2, retry_delay_seconds=15)
def sync_title_streaming(
    title: str,
    content_type: str,
    db_id: str,
    justwatch_slug: str | None = None,
    year: int | None = None,
) -> int:
    """
    Sync streaming availability for one title across all regions.

    Returns number of streaming rows upserted.
    """
    slug = justwatch_slug or title_to_slug(title, year=year)
    jw_type = "movie" if content_type == "movie" else "tv-show"
    all_rows = []

    for region in REGIONS:
        data = run_with_retry(
            get_streaming_availability,
            title,
            content_type=jw_type,
            locale=region,
            slug=slug,
        )
        if not data or not data.get("found"):
            continue

        offers = data.get("streaming_offers", [])
        for offer in offers:
            offer["region"] = region

        movie_id = db_id if content_type == "movie" else None
        show_id = db_id if content_type == "show" else None
        rows = _transform_offers(offers, movie_id=movie_id, show_id=show_id)
        all_rows.extend(rows)

        # Update JustWatch slug in DB if we didn't have it
        if not justwatch_slug and data.get("slug"):
            table = "movies" if content_type == "movie" else "tv_shows"
            _supabase.table(table) \
                .update({"justwatch_slug": data["slug"]}) \
                .eq("id", db_id) \
                .execute()

        polite_delay(1.5)

    if all_rows:
        upsert_streaming_bulk(all_rows)

    return len(all_rows)


@flow(name="sync_justwatch", log_prints=True)
def sync_justwatch_flow(
    limit: int | None = None,
    sync_movies: bool = True,
    sync_shows: bool = True,
):
    """
    Main JustWatch sync flow.

    Args:
        limit:       Max titles to process per type (None = all)
        sync_movies: Whether to sync movies
        sync_shows:  Whether to sync TV shows
    """
    logger = get_run_logger()
    titles = _get_all_titles()
    total = 0

    if sync_movies:
        movies = titles["movies"]
        if limit:
            movies = movies[:limit]
        logger.info(f"Syncing streaming for {len(movies)} movies...")

        for movie in movies:
            count = sync_title_streaming(
                title=movie["title_english"],
                content_type="movie",
                db_id=movie["id"],
                justwatch_slug=movie.get("justwatch_slug"),
                year=movie.get("release_year"),
            )
            total += count
            polite_delay(2.0)

    if sync_shows:
        shows = titles["shows"]
        if limit:
            shows = shows[:limit]
        logger.info(f"Syncing streaming for {len(shows)} shows...")

        for show in shows:
            count = sync_title_streaming(
                title=show["title_english"],
                content_type="show",
                db_id=show["id"],
                justwatch_slug=show.get("justwatch_slug"),
                year=show.get("year"),
            )
            total += count
            polite_delay(2.0)

    logger.info(f"JustWatch sync complete: {total} streaming rows upserted")


if __name__ == "__main__":
    sync_justwatch_flow(limit=3)