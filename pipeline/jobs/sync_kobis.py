"""
pipeline/jobs/sync_kobis.py — Sync Korean box office data from KOBIS.

Fetches weekly box office rankings and links them to movies in the DB.
KOBIS is the official Korean Film Council box office registry.

Schedule: Every Monday at 6am (weekly data drops on Monday)
"""

from prefect import flow, task, get_run_logger
from datetime import date, timedelta

from data_sources.kobis import (
    get_weekly_boxoffice,
    get_daily_boxoffice,
)
from db.queries import (
    upsert_boxoffice_bulk,
    get_movie_by_tmdb_id,
    _supabase,
)
from pipeline.utils import (
    get_logger,
    safe_int,
    safe_float,
    polite_delay,
)

log = get_logger("sync_kobis")


def _get_monday(target_date: date = None) -> str:
    """Get the most recent Monday as YYYYMMDD string for KOBIS API."""
    d = target_date or date.today()
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y%m%d")


def _transform_boxoffice_row(raw: dict, week_start: str, period_type: str) -> dict:
    """Transform a raw KOBIS box office entry into DB schema."""
    # Try to find the movie in our DB by KOBIS code
    kobis_code = raw.get("movieCd") or raw.get("rnum")
    movie_title = raw.get("movieNm") or raw.get("movieNmEn")

    # Look up movie_id by kobis code
    movie_id = None
    if kobis_code:
        existing = _supabase.table("movies") \
            .select("id") \
            .eq("kobis_movie_code", str(kobis_code)) \
            .execute().data
        if existing:
            movie_id = existing[0]["id"]

    # Parse week_start into date format
    try:
        from datetime import datetime
        week_date = datetime.strptime(week_start, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        week_date = week_start

    return {
        "kobis_movie_code": str(kobis_code) if kobis_code else None,
        "movie_id":         movie_id,
        "week_start":       week_date,
        "period_type":      period_type,
        "rank":             safe_int(raw.get("rank")),
        "audience_count":   safe_int(raw.get("audiCnt") or raw.get("audiAcc")),
        "sales_amount":     safe_int(raw.get("salesAmt") or raw.get("salesAcc")),
        "sales_share":      safe_float(raw.get("salesShare")),
        "screen_count":     safe_int(raw.get("scrnCnt")),
    }


@task(retries=3, retry_delay_seconds=10)
def sync_weekly_boxoffice(target_date: str | None = None) -> int:
    """
    Sync weekly box office rankings from KOBIS.

    Args:
        target_date: YYYYMMDD string. Defaults to most recent Monday.

    Returns:
        Number of rows upserted.
    """
    week_start = target_date or _get_monday()
    log.info(f"Syncing weekly box office for week of {week_start}...")

    raw_results = get_weekly_boxoffice(target_dt=week_start)
    if not raw_results:
        log.warning(f"No box office data for {week_start}")
        return 0

    rows = [_transform_boxoffice_row(r, week_start, "weekly") for r in raw_results]
    rows = [r for r in rows if r.get("kobis_movie_code")]
    upsert_boxoffice_bulk(rows)

    log.info(f"Upserted {len(rows)} weekly box office rows")
    return len(rows)


@task(retries=3, retry_delay_seconds=10)
def sync_daily_boxoffice(target_date: str | None = None) -> int:
    """Sync daily box office rankings from KOBIS."""
    from datetime import datetime
    day = target_date or datetime.now().strftime("%Y%m%d")
    log.info(f"Syncing daily box office for {day}...")

    raw_results = get_daily_boxoffice(target_dt=day)
    if not raw_results:
        return 0

    rows = [_transform_boxoffice_row(r, day, "daily") for r in raw_results]
    rows = [r for r in rows if r.get("kobis_movie_code")]
    upsert_boxoffice_bulk(rows)

    log.info(f"Upserted {len(rows)} daily box office rows")
    return len(rows)


@task(retries=2, retry_delay_seconds=10)
def sync_historical_boxoffice(years_back: int = 10) -> int:
    """
    Sync historical weekly box office data going back N years.
    Used for initial population only — runs once.
    """
    log.info(f"Syncing historical box office ({years_back} years)...")
    total = 0

    target = date.today()
    # Go back week by week
    weeks_back = years_back * 52
    for _ in range(weeks_back):
        target -= timedelta(weeks=1)
        week_str = target.strftime("%Y%m%d")
        try:
            raw_results = get_weekly_boxoffice(target_dt=week_str)
            if raw_results:
                rows = [_transform_boxoffice_row(r, week_str, "weekly") for r in raw_results]
                rows = [r for r in rows if r.get("kobis_movie_code")]
                upsert_boxoffice_bulk(rows)
                total += len(rows)
        except Exception as e:
            log.warning(f"Failed for week {week_str}: {e}")
        polite_delay(0.5)

    log.info(f"Historical sync complete: {total} rows")
    return total


@flow(name="sync_kobis", log_prints=True)
def sync_kobis_flow(
    mode: str = "weekly",
    historical_years: int = 10,
    target_date: str | None = None,
):
    """
    Main KOBIS sync flow.

    Args:
        mode:             'weekly' (default), 'daily', or 'historical'
        historical_years: Years to go back when mode='historical'
        target_date:      YYYYMMDD override for weekly/daily modes
    """
    logger = get_run_logger()

    if mode == "historical":
        logger.info(f"Running historical KOBIS sync ({historical_years} years)...")
        total = sync_historical_boxoffice(historical_years)
        logger.info(f"Historical sync complete: {total} rows")

    elif mode == "daily":
        total = sync_daily_boxoffice(target_date)
        logger.info(f"Daily sync complete: {total} rows")

    else:  # weekly (default)
        total = sync_weekly_boxoffice(target_date)
        logger.info(f"Weekly sync complete: {total} rows")


if __name__ == "__main__":
    # Test: sync current week
    sync_kobis_flow(mode="weekly")