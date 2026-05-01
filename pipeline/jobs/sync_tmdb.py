"""
pipeline/jobs/sync_tmdb.py — Sync Korean movies and TV shows from TMDB.

This is the seed job — it populates the core movies and tv_shows tables
that all other jobs enrich with additional data.

Fetches:
- Korean movies (discover + popular + top rated)
- Korean TV shows (discover + popular + top rated)
- Cast and crew for each title
- Per-title details (genres, runtime, etc.)

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
    get_trending_korean,
)
from db.queries import (
    upsert_movie,
    upsert_show,
    upsert_person,
    upsert_movie_cast,
    upsert_show_cast,
    get_movie_by_tmdb_id,
    get_show_by_tmdb_id,
)
from pipeline.utils import (
    get_logger,
    parse_date,
    extract_year,
    normalize_genres,
    safe_float,
    safe_int,
    parse_runtime_minutes,
    map_tmdb_status,
    polite_delay,
    run_with_retry,
    batch,
)

log = get_logger("sync_tmdb")


# ── transformers ──────────────────────────────────────────────────────────────

def _transform_movie(raw: dict) -> dict:
    """Transform raw TMDB movie details into DB schema."""
    genres = normalize_genres([g["name"] for g in raw.get("genres", [])])

    return {
        "tmdb_id":           str(raw["id"]),
        "title_english":     raw.get("title") or raw.get("original_title", "Unknown"),
        "title_korean":      raw.get("original_title") if raw.get("original_language") == "ko" else None,
        "synopsis_short":    raw.get("overview"),
        "release_year":      extract_year(raw.get("release_date")),
        "release_date":      parse_date(raw.get("release_date")),
        "runtime_minutes":   safe_int(raw.get("runtime")),
        "genres":            genres,
        "status":            raw.get("status"),
        "country":           "South Korea",
        "poster_url":        f"https://image.tmdb.org/t/p/w500{raw['poster_path']}" if raw.get("poster_path") else None,
        "tmdb_rating":       safe_float(raw.get("vote_average")),
    }


def _transform_show(raw: dict) -> dict:
    """Transform raw TMDB TV show details into DB schema."""
    genres = normalize_genres([g["name"] for g in raw.get("genres", [])])
    networks = raw.get("networks", [])
    network = networks[0]["name"] if networks else None

    return {
        "tmdb_id":           str(raw["id"]),
        "title_english":     raw.get("name") or raw.get("original_name", "Unknown"),
        "title_korean":      raw.get("original_name") if raw.get("original_language") == "ko" else None,
        "synopsis_short":    raw.get("overview"),
        "year":              extract_year(raw.get("first_air_date")),
        "first_air_date":    parse_date(raw.get("first_air_date")),
        "last_air_date":     parse_date(raw.get("last_air_date")),
        "status":            map_tmdb_status(raw.get("status")),
        "total_episodes":    safe_int(raw.get("number_of_episodes")),
        "genres":            genres,
        "network":           network,
        "content_type":      "Korean Drama",
        "poster_url":        f"https://image.tmdb.org/t/p/w500{raw['poster_path']}" if raw.get("poster_path") else None,
        "tmdb_rating":       safe_float(raw.get("vote_average")),
    }


def _transform_person(raw: dict) -> dict:
    """Transform raw TMDB person into DB schema."""
    return {
        "tmdb_person_id":        str(raw["id"]),
        "name_english":          raw.get("name", "Unknown"),
        "known_for_department":  raw.get("known_for_department"),
        "profile_url":           f"https://image.tmdb.org/t/p/w185{raw['profile_path']}" if raw.get("profile_path") else None,
    }


# ── tasks ─────────────────────────────────────────────────────────────────────

@task(retries=3, retry_delay_seconds=10, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=12))
def fetch_korean_movie_ids() -> list[int]:
    """Fetch all Korean movie IDs from TMDB discover endpoint."""
    log.info("Fetching Korean movie IDs from TMDB...")
    all_ids = set()

    # Discover all Korean movies, page through results
    page = 1
    while True:
        results = discover_korean_content(content_type="movie", page=page)
        if not results:
            break
        for r in results:
            all_ids.add(r["id"])
        if len(results) < 20:
            break
        page += 1
        if page > 500:  # TMDB max pages
            break
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
        results = discover_korean_content(content_type="tv", page=page)
        if not results:
            break
        for r in results:
            all_ids.add(r["id"])
        if len(results) < 20:
            break
        page += 1
        if page > 500:
            break
        polite_delay(0.25)

    log.info(f"Found {len(all_ids)} Korean TV show IDs")
    return list(all_ids)


@task(retries=2, retry_delay_seconds=5)
def sync_movie(tmdb_id: int) -> dict | None:
    """Fetch full movie details from TMDB and upsert to DB."""
    raw = run_with_retry(get_movie_details, tmdb_id)
    if not raw:
        return None

    movie_data = _transform_movie(raw)
    movie_row = upsert_movie(movie_data)
    movie_db_id = movie_row.get("id")

    if not movie_db_id:
        return None

    # Sync cast
    credits = raw.get("credits", {})
    cast = credits.get("cast", [])[:20]  # top 20 cast members
    crew = credits.get("crew", [])

    # Director(s)
    directors = [c for c in crew if c.get("job") == "Director"]
    for director in directors[:2]:
        person_data = _transform_person(director)
        person_row = upsert_person(person_data)
        if person_row.get("id"):
            upsert_movie_cast(movie_db_id, person_row["id"], {
                "role_type": "Director",
                "cast_order": 0,
            })

    # Cast members
    for i, member in enumerate(cast):
        person_data = _transform_person(member)
        person_row = upsert_person(person_data)
        if person_row.get("id"):
            upsert_movie_cast(movie_db_id, person_row["id"], {
                "character_name": member.get("character"),
                "role_type": "Lead" if i < 3 else "Supporting",
                "cast_order": i + 1,
            })

    polite_delay(0.25)
    return movie_row


@task(retries=2, retry_delay_seconds=5)
def sync_show(tmdb_id: int) -> dict | None:
    """Fetch full TV show details from TMDB and upsert to DB."""
    raw = run_with_retry(get_show_details, tmdb_id)
    if not raw:
        return None

    show_data = _transform_show(raw)
    show_row = upsert_show(show_data)
    show_db_id = show_row.get("id")

    if not show_db_id:
        return None

    # Sync cast from aggregate credits
    credits = raw.get("aggregate_credits", raw.get("credits", {}))
    cast = credits.get("cast", [])[:20]
    crew = credits.get("crew", [])

    # Director(s) / Creator(s)
    creators = raw.get("created_by", [])
    for creator in creators[:2]:
        person_data = _transform_person(creator)
        person_row = upsert_person(person_data)
        if person_row.get("id"):
            upsert_show_cast(show_db_id, person_row["id"], {
                "role_type": "Director",
                "cast_order": 0,
            })

    # Cast members
    for i, member in enumerate(cast):
        person_data = _transform_person(member)
        person_row = upsert_person(person_data)
        if person_row.get("id"):
            roles = member.get("roles", [{}])
            character = roles[0].get("character") if roles else member.get("character")
            upsert_show_cast(show_db_id, person_row["id"], {
                "character_name": character,
                "role_type": "Main Role" if i < 5 else "Support Role",
                "cast_order": i + 1,
            })

    polite_delay(0.25)
    return show_row


# ── flow ──────────────────────────────────────────────────────────────────────

@flow(name="sync_tmdb", log_prints=True)
def sync_tmdb_flow(
    sync_movies: bool = True,
    sync_shows: bool = True,
    movie_limit: int = None,
    show_limit: int = None,
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

        synced = 0
        failed = 0
        for id_batch in batch(movie_ids, size=50):
            for tmdb_id in id_batch:
                result = sync_movie(tmdb_id)
                if result:
                    synced += 1
                else:
                    failed += 1
            polite_delay(1.0)  # pause between batches

        logger.info(f"Movies: {synced} synced, {failed} failed")

    if sync_shows:
        show_ids = fetch_korean_show_ids()
        if show_limit:
            show_ids = show_ids[:show_limit]
        logger.info(f"Syncing {len(show_ids)} Korean TV shows...")

        synced = 0
        failed = 0
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