"""
pipeline/jobs/sync_naver_tv.py — Sync episode ratings and OST albums from Naver.

Enriches tv_shows with:
- Per-episode Nielsen Korea viewership ratings
- OST album listings with Naver Vibe links
- Latest and peak episode ratings

This data is unique — no other English-language source has
structured per-episode Korean viewership data.

Schedule: Nightly at 4am
"""

from prefect import flow, task, get_run_logger

from data_sources.naver_tv import get_drama_broadcast_info
from db.queries import (
    upsert_show,
    upsert_episodes_bulk,
    upsert_ost_albums_bulk,
    _supabase,
)
from pipeline.utils import (
    get_logger,
    parse_naver_air_date,
    safe_float,
    safe_int,
    polite_delay,
    run_with_retry,
)

log = get_logger("sync_naver_tv")


def _get_shows_with_korean_titles() -> list[dict]:
    """
    Get all TV shows from the DB that have Korean titles.
    These can be searched on Naver by their Korean title.
    """
    result = _supabase.table("tv_shows") \
        .select("id, title_english, title_korean, year, naver_show_id") \
        .not_.is_("title_korean", "null") \
        .execute()
    return result.data or []


def _transform_episodes(show_id: str, episodes: list[dict], show_year: int = None) -> list[dict]:
    """Transform Naver episode data into DB schema."""
    rows = []
    for ep in episodes:
        if not ep.get("episode") or ep.get("rating") is None:
            continue

        # Parse air date — Naver gives MM.DD. format
        air_date = parse_naver_air_date(
            ep.get("air_date"),
            base_year=show_year
        )

        rows.append({
            "episode_number": safe_int(ep["episode"]),
            "air_date":       air_date,
            "nielsen_rating": safe_float(ep["rating"]),
            "channel":        ep.get("channel"),
        })
    return rows


def _transform_ost_albums(albums: list[dict]) -> list[dict]:
    """Transform Naver OST album data into DB schema."""
    rows = []
    for album in albums:
        if not album.get("album_name"):
            continue
        rows.append({
            "album_name":   album["album_name"],
            "artist":       album.get("artist"),
            "release_date": album.get("release_date"),
            "cover_url":    album.get("cover_url"),
            "vibe_url":     album.get("vibe_url"),
        })
    return rows


@task(retries=2, retry_delay_seconds=15)
def sync_show_naver_data(show: dict) -> bool:
    """
    Fetch and sync Naver data for one TV show.
    Uses the Korean title for Naver search.
    """
    korean_title = show.get("title_korean")
    show_id = show.get("id")
    show_year = show.get("year")

    if not korean_title or not show_id:
        return False

    log.info(f"Syncing Naver data for: {korean_title}")

    data = run_with_retry(get_drama_broadcast_info, korean_title)
    if not data:
        return False

    # Update show with latest/peak ratings
    updates = {}
    if data.get("latest_rating") is not None:
        updates["naver_latest_rating"] = safe_float(data["latest_rating"])
    if data.get("highest_rating") is not None:
        updates["naver_highest_rating"] = safe_float(data["highest_rating"])
    if data.get("latest_episode") is not None:
        updates["naver_latest_episode"] = safe_int(data["latest_episode"])
    if data.get("channel") and not show.get("network"):
        updates["network"] = data["channel"]

    if updates:
        _supabase.table("tv_shows") \
            .update(updates) \
            .eq("id", show_id) \
            .execute()

    # Sync per-episode ratings
    if data.get("episodes"):
        episode_rows = _transform_episodes(show_id, data["episodes"], show_year)
        if episode_rows:
            upsert_episodes_bulk(show_id, episode_rows)
            log.info(f"  {len(episode_rows)} episode ratings synced")

    # Sync OST albums
    if data.get("ost_albums"):
        album_rows = _transform_ost_albums(data["ost_albums"])
        if album_rows:
            upsert_ost_albums_bulk(show_id, album_rows)
            log.info(f"  {len(album_rows)} OST albums synced")

    return True


@flow(name="sync_naver_tv", log_prints=True)
def sync_naver_tv_flow(limit: int | None = None, only_airing: bool = False):
    """
    Main Naver TV sync flow.

    Args:
        limit:        Max shows to process (None = all)
        only_airing:  If True, only sync currently airing shows
                      (faster for nightly updates)
    """
    logger = get_run_logger()

    shows = _get_shows_with_korean_titles()

    if only_airing:
        shows = [s for s in shows if s.get("status") == "Airing"]
        logger.info(f"Syncing {len(shows)} airing shows...")
    else:
        logger.info(f"Syncing {len(shows)} shows with Korean titles...")

    if limit:
        shows = shows[:limit]

    synced = 0
    failed = 0
    for show in shows:
        result = sync_show_naver_data(show)
        if result:
            synced += 1
        else:
            failed += 1
        polite_delay(3.0)  # Naver needs longer delays

    logger.info(f"Naver TV sync complete: {synced} synced, {failed} failed")


if __name__ == "__main__":
    sync_naver_tv_flow(limit=3, only_airing=True)