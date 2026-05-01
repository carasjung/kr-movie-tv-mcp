"""
pipeline/jobs/sync_wikipedia.py — Sync Wikipedia content for Korean titles.

Enriches movies and tv_shows with:
- Full plot summaries
- Production background
- Critical reception text
- Accolades sections

Schedule: Weekly on Thursday at 4am
"""

from prefect import flow, task, get_run_logger

from data_sources.wikipedia import get_korean_title_info
from db.queries import _supabase
from pipeline.utils import (
    get_logger,
    polite_delay,
    run_with_retry,
)

log = get_logger("sync_wikipedia")

MOVIE_SECTIONS = ["Plot", "Production", "Reception", "Accolades"]
SHOW_SECTIONS = ["Plot", "Cast", "Production", "Reception", "Ratings"]


@task(retries=2, retry_delay_seconds=10)
def sync_title_wikipedia(
    title: str,
    db_id: str,
    content_type: str,
    year: int = None,
    wikipedia_title: str = None,
) -> bool:
    """Fetch and sync Wikipedia sections for one title."""
    sections = MOVIE_SECTIONS if content_type == "movie" else SHOW_SECTIONS
    wiki_type = "film" if content_type == "movie" else "TV series"

    data = run_with_retry(
        get_korean_title_info,
        wikipedia_title or title,
        year=year,
        content_type=wiki_type,
        sections=sections,
    )

    if not data or not data.get("found"):
        return False

    # Build wiki_sections dict from fetched sections
    wiki_sections = {}
    for section_name, content in (data.get("sections") or {}).items():
        if content:
            wiki_sections[section_name] = content

    if not wiki_sections:
        return False

    # Update the title record with wiki data
    updates = {"wiki_sections": wiki_sections}
    if data.get("wikipedia_title"):
        updates["wikipedia_title"] = data["wikipedia_title"]
    if data.get("summary") and not wiki_sections.get("Plot"):
        # Use summary as synopsis_full if no plot section
        updates["synopsis_full"] = data["summary"]

    table = "movies" if content_type == "movie" else "tv_shows"
    _supabase.table(table) \
        .update(updates) \
        .eq("id", db_id) \
        .execute()

    return True


@flow(name="sync_wikipedia", log_prints=True)
def sync_wikipedia_flow(
    limit: int = None,
    sync_movies: bool = True,
    sync_shows: bool = True,
    skip_existing: bool = True,
):
    """
    Main Wikipedia sync flow.

    Args:
        limit:         Max titles to process per type
        sync_movies:   Whether to sync movies
        sync_shows:    Whether to sync TV shows
        skip_existing: Skip titles that already have wiki_sections
    """
    logger = get_run_logger()
    total_synced = 0

    if sync_movies:
        query = _supabase.table("movies").select("id, title_english, release_year, wikipedia_title")
        if skip_existing:
            query = query.is_("wiki_sections", "null")
        movies = query.execute().data or []

        if limit:
            movies = movies[:limit]

        logger.info(f"Syncing Wikipedia for {len(movies)} movies...")
        for movie in movies:
            result = sync_title_wikipedia(
                title=movie["title_english"],
                db_id=movie["id"],
                content_type="movie",
                year=movie.get("release_year"),
                wikipedia_title=movie.get("wikipedia_title"),
            )
            if result:
                total_synced += 1
            polite_delay(1.0)

    if sync_shows:
        query = _supabase.table("tv_shows").select("id, title_english, year, wikipedia_title")
        if skip_existing:
            query = query.is_("wiki_sections", "null")
        shows = query.execute().data or []

        if limit:
            shows = shows[:limit]

        logger.info(f"Syncing Wikipedia for {len(shows)} shows...")
        for show in shows:
            result = sync_title_wikipedia(
                title=show["title_english"],
                db_id=show["id"],
                content_type="show",
                year=show.get("year"),
                wikipedia_title=show.get("wikipedia_title"),
            )
            if result:
                total_synced += 1
            polite_delay(1.0)

    logger.info(f"Wikipedia sync complete: {total_synced} titles enriched")


if __name__ == "__main__":
    sync_wikipedia_flow(limit=3)