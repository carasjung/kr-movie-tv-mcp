"""
pipeline/orchestrator.py — Master pipeline that orchestrates all sync jobs.

Two modes:
1. Initial population: runs everything deeply (takes hours)
2. Nightly sync: runs only what needs daily updates

Schedule: 
  - Initial population: run once manually
  - Nightly sync: 2am daily via Prefect Cloud deployment
"""

from prefect import flow, get_run_logger
from datetime import date

from pipeline.jobs.sync_tmdb import sync_tmdb_flow
from pipeline.jobs.sync_kobis import sync_kobis_flow
from pipeline.jobs.sync_mydramalist import sync_mdl_flow
from pipeline.jobs.sync_naver_tv import sync_naver_tv_flow
from pipeline.jobs.sync_justwatch import sync_justwatch_flow
from pipeline.jobs.sync_wikipedia import sync_wikipedia_flow
from pipeline.jobs.sync_awards import sync_awards_flow


@flow(name="initial_population", log_prints=True)
def initial_population_flow():
    """
    Run once to populate the database from scratch.
    This will take several hours — run overnight.

    Order matters:
    1. TMDB first — seeds core titles (movies + shows)
    2. MDL second — enriches shows with ratings/tags
    3. KOBIS — historical box office
    4. Naver TV — episode ratings + OST
    5. JustWatch — streaming availability
    6. Wikipedia — plot summaries
    7. Awards — ceremony history
    """
    logger = get_run_logger()
    logger.info("=== Starting initial database population ===")
    logger.info(f"Date: {date.today()}")

    # Step 1: Seed all Korean movies and TV shows from TMDB
    logger.info("\n[1/7] TMDB — seeding core titles...")
    sync_tmdb_flow(sync_movies=True, sync_shows=True)

    # Step 2: Enrich shows with MDL data
    logger.info("\n[2/7] MyDramaList — enriching shows...")
    sync_mdl_flow()

    # Step 3: Historical box office from KOBIS
    logger.info("\n[3/7] KOBIS — historical box office (10 years)...")
    sync_kobis_flow(mode="historical", historical_years=10)

    # Step 4: Episode ratings + OST from Naver
    logger.info("\n[4/7] Naver TV — episode ratings + OST...")
    sync_naver_tv_flow()

    # Step 5: Streaming availability from JustWatch
    logger.info("\n[5/7] JustWatch — streaming availability...")
    sync_justwatch_flow()

    # Step 6: Wikipedia sections
    logger.info("\n[6/7] Wikipedia — plot summaries + context...")
    sync_wikipedia_flow()

    # Step 7: Awards history
    logger.info("\n[7/7] Awards — ceremony history (10 years)...")
    sync_awards_flow(years_back=10)

    logger.info("\n=== Initial population complete ===")


@flow(name="nightly_sync", log_prints=True)
def nightly_sync_flow():
    """
    Nightly sync — runs every day at 2am.
    Only syncs data that changes frequently.
    Fast — should complete in under 30 minutes.
    """
    logger = get_run_logger()
    logger.info(f"=== Nightly sync starting: {date.today()} ===")

    # TMDB — new titles and rating updates
    logger.info("[1] TMDB nightly update...")
    sync_tmdb_flow(sync_movies=True, sync_shows=True, movie_limit=200, show_limit=200)

    # MDL — airing status and ratings change daily
    logger.info("[2] MDL nightly update...")
    sync_mdl_flow(limit=100)

    # Naver TV — episode ratings for airing shows only
    logger.info("[3] Naver TV — airing shows...")
    sync_naver_tv_flow(only_airing=True)

    logger.info("=== Nightly sync complete ===")


@flow(name="weekly_sync", log_prints=True)
def weekly_sync_flow():
    """
    Weekly sync — runs every Monday at 6am.
    Syncs data that changes less frequently.
    """
    logger = get_run_logger()
    logger.info(f"=== Weekly sync starting: {date.today()} ===")

    # KOBIS — weekly box office
    logger.info("[1] KOBIS weekly box office...")
    sync_kobis_flow(mode="weekly")

    # JustWatch — streaming catalog
    logger.info("[2] JustWatch streaming...")
    sync_justwatch_flow(limit=500)

    # Wikipedia — new titles only
    logger.info("[3] Wikipedia new titles...")
    sync_wikipedia_flow(skip_existing=True)

    # Awards — check for new ceremonies
    logger.info("[4] Awards update...")
    sync_awards_flow(years_back=2)

    logger.info("=== Weekly sync complete ===")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "nightly"

    if mode == "initial":
        initial_population_flow()
    elif mode == "weekly":
        weekly_sync_flow()
    else:
        nightly_sync_flow()