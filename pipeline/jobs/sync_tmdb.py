"""
pipeline/jobs/sync_tmdb.py — Sync Korean movies and TV shows from TMDB.

This is the seed job — it populates the core movies and tv_shows tables
that all other jobs enrich with additional data.

Schedule: Nightly at 2am
"""

import time
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta

from data_sources.tmdb import (
    discover_korean_content,
    get_movie_details,
    get_show_details,
)
from db.queries import (
    upsert_movie,
    upsert_show,
    upsert_person,
    upsert_movie_cast,
    upsert_show_cast,
)
from pipeline.utils import (
    get_logger,
    parse_date,
    extract_year,
    normalize_genres,
    safe_float,
    safe_int,
    map_tmdb_status,
    polite_delay,
    run_with_retry,
    batch,
)

log = get_logger("sync_tmdb")


# ── transformers ──────────────────────────────────────────────────────────────

def _transform_movie(raw: dict) -> dict:
    """Transform normalized TMDB movie details into DB schema."""
    return {
        "tmdb_id":           str(raw["id"]),
        "title_english":     raw.get("title") or raw.get("original_title", "Unknown"),
        "title_korean":      raw.get("original_title") if raw.get("original_language") == "ko" else None,
        "synopsis_short":    raw.get("overview"),
        "release_year":      extract_year(raw.get("release_date")),
        "release_date":      parse_date(raw.get("release_date")),
        "runtime_minutes":   safe_int(raw.get("runtime_minutes")),
        "genres":            normalize_genres(raw.get("genres", [])),
        "status":            raw.get("status"),
        "country":           "South Korea",
        "poster_url":        raw.get("poster_url"),
        "tmdb_rating":       safe_float(raw.get("rating")),
    }


def _transform_show(raw: dict) -> dict:
    """Transform normalized TMDB TV show details into DB schema."""
    networks = raw.get("networks", [])
    network = networks[0] if networks else None

    return {
        "tmdb_id":           str(raw["id"]),
        "title_english":     raw.get("title") or raw.get("original_title", "Unknown"),
        "title_korean":      raw.get("original_title") if raw.get("original_language") == "ko" else None,
        "synopsis_short":    raw.get("overview"),
        "year":              extract_year(raw.get("first_air_date")),
        "first_air_date":    parse_date(raw.get("first_air_date")),
        "last_air_date":     parse_date(raw.get("last_air_date")),
        "status":            map_tmdb_status(raw.get("status")),
        "total_episodes":    safe_int(raw.get("total_episodes")),
        "genres":            normalize_genres(raw.get("genres", [])),
        "network":           network,
        "content_type":      "Korean Drama",
        "poster_url":        raw.get("poster_url"),
        "tmdb_rating":       safe_float(raw.get("rating")),
    }


def _build_person_data(tmdb_id: int, member: dict) -> dict:
    """Build a person record from a normalized TMDB cast member."""
    return {
        "tmdb_person_id":       f"tmdb_{tmdb_id}_{member['name'].replace(' ', '_')}",
        "name_english":         member.get("name", "Unknown"),
        "name_korean":          member.get("korean_name"),
        "profile_url":          member.get("profile_url"),
        "known_for_department": "Acting",
    }


# ── tasks ─────────────────────────────────────────────────────────────────────

@task(retries=3, retry_delay_seconds=10, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=12))
def fetch_korean_movie_ids() -> list[int]:
    """Fetch all Korean movie IDs from TMDB discover endpoint."""
    log.info("Fetching Korean movie IDs from TMDB...")
    all_ids = set()

    page = 1
    while True:
        response = discover_korean_content(content_type="movie", page=page)
        if not response:
            break
        # Unwrap results list from response dict
        results = response.get("results", []) if isinstance(response, dict) else response
        if not results:
            break
        for r in results:
            all_ids.add(r["id"])
        total_pages = response.get("total_pages", 1) if isinstance(response, dict) else 1
        if page >= total_pages or page >= 500:
            break
        page += 1
        polite_delay(0.25)

    log.info(f"Found {len(all_ids)} Korean movie IDs")
    return list(all_ids)


@task(retries=3, retry_delay_seconds=10, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=12))
def fetch_korean_show_ids() -> list[int]:
    """Fetch all Korean TV show IDs from TMDB discover endpoint."""
    log.info("Fetching Korean TV show IDs from TMDB...")
    all_ids = set()

    page = 1
    while True:
        response = discover_korean_content(content_type="tv", page=page)
        if not response:
            break
        results = response.get("results", []) if isinstance(response, dict) else response
        if not results:
            break
        for r in results:
            all_ids.add(r["id"])
        total_pages = response.get("total_pages", 1) if isinstance(response, dict) else 1
        if page >= total_pages or page >= 500:
            break
        page += 1
        polite_delay(0.25)

    log.info(f"Found {len(all_ids)} Korean TV show IDs")
    return list(all_ids)


@task(retries=2, retry_delay_seconds=5)
def sync_movie(tmdb_id: int) -> dict | None:
    """Fetch full movie details from TMDB and upsert to DB."""
    raw = run_with_retry(get_movie_details, tmdb_id)
    if not raw:
        return None

    movie_row = upsert_movie(_transform_movie(raw))
    movie_db_id = movie_row.get("id")
    if not movie_db_id:
        return None

    # Sync cast
    cast = raw.get("cast", [])[:20]
    for i, member in enumerate(cast):
        person_row = upsert_person(_build_person_data(tmdb_id, member))
        if person_row.get("id"):
            upsert_movie_cast(movie_db_id, person_row["id"], {
                "character_name": member.get("character"),
                "role_type":      "Lead" if i < 3 else "Supporting",
                "cast_order":     i + 1,
            })

    polite_delay(0.25)
    return movie_row


@task(retries=2, retry_delay_seconds=5)
def sync_show(tmdb_id: int) -> dict | None:
    """Fetch full TV show details from TMDB and upsert to DB."""
    raw = run_with_retry(get_show_details, tmdb_id)
    if not raw:
        return None

    show_row = upsert_show(_transform_show(raw))
    show_db_id = show_row.get("id")
    if not show_db_id:
        return None

    # Sync cast — already normalized by tmdb.py
    cast = raw.get("cast", [])[:20]
    for i, member in enumerate(cast):
        person_row = upsert_person(_build_person_data(tmdb_id, member))
        if person_row.get("id"):
            upsert_show_cast(show_db_id, person_row["id"], {
                "character_name": member.get("character"),
                "role_type":      "Main Role" if i < 5 else "Support Role",
                "cast_order":     i + 1,
            })

    polite_delay(0.25)
    return show_row


# ── flow ──────────────────────────────────────────────────────────────────────

@flow(name="sync_tmdb", log_prints=True)
def sync_tmdb_flow(
    sync_movies: bool = True,
    sync_shows: bool = True,
    movie_limit: int | None = None,
    show_limit: int | None = None,
):
    """
    Main TMDB sync flow. Fetches all Korean movies and TV shows.

    Args:
        sync_movies:  Whether to sync movies
        sync_shows:   Whether to sync TV shows
        movie_limit:  Max movies to sync (None = all)
        show_limit:   Max shows to sync (None = all)
    """
    logger = get_run_logger()

    if sync_movies:
        movie_ids = fetch_korean_movie_ids()
        if movie_limit:
            movie_ids = movie_ids[:movie_limit]
        logger.info(f"Syncing {len(movie_ids)} Korean movies...")

        synced = failed = 0
        for id_batch in batch(movie_ids, size=50):
            for tmdb_id in id_batch:
                result = sync_movie(tmdb_id)
                if result:
                    synced += 1
                else:
                    failed += 1
            polite_delay(1.0)

        logger.info(f"Movies: {synced} synced, {failed} failed")

    if sync_shows:
        show_ids = fetch_korean_show_ids()
        if show_limit:
            show_ids = show_ids[:show_limit]
        logger.info(f"Syncing {len(show_ids)} Korean TV shows...")

        synced = failed = 0
        for id_batch in batch(show_ids, size=50):
            for tmdb_id in id_batch:
                result = sync_show(tmdb_id)
                if result:
                    synced += 1
                else:
                    failed += 1
            polite_delay(1.0)

        logger.info(f"Shows: {synced} synced, {failed} failed")

    logger.info("TMDB sync complete.")


if __name__ == "__main__":
    # Quick test: sync 5 movies and 5 shows
    sync_tmdb_flow(movie_limit=5, show_limit=5)