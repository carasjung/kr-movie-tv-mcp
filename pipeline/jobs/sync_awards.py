"""
pipeline/jobs/sync_awards.py — Sync Korean entertainment awards data.

Sources:
- AsianWiki: KBS, MBC, SBS Drama Awards + Blue Dragon Film/Series Awards
- Baeksang official site: Baeksang Arts Awards

Enriches the awards and award_nominees tables.

Schedule: Weekly on Sunday at 5am
"""

from prefect import flow, task, get_run_logger

from data_sources.awards import (
    get_awards,
    get_baeksang_winners,
    _get_ceremony_years,
)
from db.queries import (
    upsert_award,
    upsert_award_nominees_bulk,
    _supabase,
)
from pipeline.utils import (
    get_logger,
    polite_delay,
    run_with_retry,
)

log = get_logger("sync_awards")

CEREMONIES = ["kbs_drama", "mbc_drama", "sbs_drama", "blue_dragon", "blue_dragon_ott"]


def _find_title_id(title: str, content_type: str = "show") -> str | None:
    """Try to find a movie or show ID by title match."""
    if not title:
        return None
    table = "tv_shows" if content_type == "show" else "movies"
    result = _supabase.table(table) \
        .select("id") \
        .ilike("title_english", f"%{title}%") \
        .limit(1) \
        .execute()
    return result.data[0]["id"] if result.data else None


def _is_film_ceremony(ceremony_key: str) -> bool:
    return "dragon" in ceremony_key.lower()


@task(retries=2, retry_delay_seconds=10)
def sync_ceremony_year(ceremony_key: str, year: int) -> int:
    """Sync one ceremony year from AsianWiki."""
    log.info(f"Syncing {ceremony_key} {year}...")
    is_film = _is_film_ceremony(ceremony_key)

    data = run_with_retry(get_awards, ceremony_key, year)
    if not data or not data.get("categories"):
        log.warning(f"  No data for {ceremony_key} {year}")
        return 0

    ceremony_name = data["ceremony"]
    count = 0

    for cat in data["categories"]:
        if not cat.get("winner_name"):
            continue

        winner_show = cat.get("winner_show")
        winner_name = cat.get("winner_name")

        # Try to link to movie or show in DB
        movie_id = _find_title_id(winner_show or winner_name, "movie") if is_film else None
        show_id = _find_title_id(winner_show, "show") if not is_film else None

        award_data = {
            "ceremony":    ceremony_name,
            "year":        year,
            "category":    cat["category"],
            "winner_name": winner_name,
            "winner_show": winner_show,
            "movie_id":    movie_id,
            "show_id":     show_id,
            "won":         True,
        }

        award_row = upsert_award(award_data)
        award_id = award_row.get("id") if award_row else None

        # Sync nominees
        if award_id and cat.get("nominees"):
            nominee_rows = []
            for nom in cat["nominees"]:
                nom_show = nom.get("show")
                nom_name = nom.get("name")
                nom_movie_id = _find_title_id(nom_show or nom_name, "movie") if is_film else None
                nom_show_id = _find_title_id(nom_show, "show") if not is_film else None
                nominee_rows.append({
                    "nominee_name": nom_name,
                    "nominee_show": nom_show,
                    "movie_id":     nom_movie_id,
                    "show_id":      nom_show_id,
                })
            upsert_award_nominees_bulk(award_id, nominee_rows)

        count += 1
        polite_delay(0.2)

    log.info(f"  {count} categories synced for {ceremony_key} {year}")
    return count


@task(retries=2, retry_delay_seconds=15)
def sync_baeksang_year(year: int) -> int:
    """Sync one Baeksang Arts Awards year from official site."""
    log.info(f"Syncing Baeksang {year}...")

    data = run_with_retry(get_baeksang_winners, year)
    if not data or data.get("total_categories", 0) == 0:
        log.warning(f"  No Baeksang data for {year}")
        return 0

    count = 0

    # Grand prizes
    for gp in data.get("grand_prizes", []):
        category = gp.get("category", "").replace("\n", " ").strip()
        winner = gp.get("winner")
        if not winner:
            continue

        is_film = "movie" in category.lower()
        movie_id = _find_title_id(winner, "movie") if is_film else None
        show_id = _find_title_id(winner, "show") if not is_film else None

        upsert_award({
            "ceremony":    "Baeksang Arts Awards",
            "year":        year,
            "category":    category,
            "winner_name": winner,
            "movie_id":    movie_id,
            "show_id":     show_id,
            "won":         True,
        })
        count += 1

    # Category winners
    for winner_data in data.get("winners", []):
        category = winner_data.get("category")
        winner = winner_data.get("winner")
        if not category or not winner:
            continue

        is_film = "film" in category.lower() or "movie" in category.lower() or "cinema" in category.lower()
        movie_id = _find_title_id(winner, "movie") if is_film else None
        show_id = _find_title_id(winner, "show") if not is_film else None

        upsert_award({
            "ceremony":    "Baeksang Arts Awards",
            "year":        year,
            "category":    category,
            "winner_name": winner,
            "winner_show": winner_data.get("studio"),
            "movie_id":    movie_id,
            "show_id":     show_id,
            "won":         True,
        })
        count += 1

    log.info(f"  {count} Baeksang categories synced for {year}")
    return count


@flow(name="sync_awards", log_prints=True)
def sync_awards_flow(
    years_back: int = 10,
    include_baeksang: bool = True,
    ceremony_keys: list[str] | None = None,
):
    """
    Main awards sync flow.

    Args:
        years_back:        How many years of history to sync
        include_baeksang:  Whether to sync Baeksang Awards
        ceremony_keys:     Specific ceremonies to sync (None = all)
    """
    logger = get_run_logger()
    ceremonies = ceremony_keys or CEREMONIES
    total = 0

    # AsianWiki ceremonies
    for ceremony_key in ceremonies:
        try:
            years = _get_ceremony_years(ceremony_key)[:years_back]
        except Exception as e:
            logger.warning(f"Could not get years for {ceremony_key}: {e}")
            continue

        for year_info in years:
            count = sync_ceremony_year(ceremony_key, year_info["year"])
            total += count
            polite_delay(1.0)

    # Baeksang
    if include_baeksang:
        from datetime import date
        current_year = date.today().year
        for year in range(current_year, current_year - years_back, -1):
            count = sync_baeksang_year(year)
            total += count
            polite_delay(2.0)

    logger.info(f"Awards sync complete: {total} total categories synced")


if __name__ == "__main__":
    sync_awards_flow(years_back=3, include_baeksang=True)