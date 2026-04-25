"""
KOBIS (Korean Film Council) Open API data source.
Provides Korean box office data — daily, weekly, and weekend rankings.

API Docs: https://www.kobis.or.kr/kobisopenapi
Contact:  openapimaster@kofic.or.kr
"""

import os
from datetime import date, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

KOBIS_API_KEY = os.getenv("KOBIS_API_KEY")
BASE_URL = "http://www.kobis.or.kr/kobisopenapi/webservice/rest"


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = {}) -> dict:
    """Make a GET request to the KOBIS API. Raises on HTTP errors."""
    if not KOBIS_API_KEY:
        raise ValueError("KOBIS_API_KEY is not set in your .env file.")

    response = requests.get(
        f"{BASE_URL}{endpoint}",
        params={"key": KOBIS_API_KEY, "itemPerPage": 10, **params},
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def _prev_weekday(target_date: date, weekday: int) -> date:
    """
    Return the most recent occurrence of a weekday before target_date.
    weekday: 0=Monday ... 6=Sunday
    """
    days_behind = (target_date.weekday() - weekday) % 7
    if days_behind == 0:
        days_behind = 7
    return target_date - timedelta(days=days_behind)


def _format_daily_entry(entry: dict) -> dict:
    """Normalize a single daily box office entry."""
    return {
        "rank": int(entry.get("rank", 0)),
        "rank_change": int(entry.get("rankInten", 0)),   # positive = up, negative = down
        "is_new_entry": entry.get("rankOldAndNew") == "NEW",
        "movie_code": entry.get("movieCd"),
        "title": entry.get("movieNm"),
        "release_date": entry.get("openDt"),
        "sales_amount": int(entry.get("salesAmt", 0)),          # KRW
        "sales_share": float(entry.get("salesShare", 0)),        # % of total sales
        "sales_change": int(entry.get("salesInten", 0)),         # change from prev day
        "sales_change_pct": float(entry.get("salesChange", 0)),  # % change
        "audience_count": int(entry.get("audiCnt", 0)),          # admissions that day
        "audience_change": int(entry.get("audiInten", 0)),
        "audience_change_pct": float(entry.get("audiChange", 0)),
        "cumulative_audience": int(entry.get("audiAcc", 0)),     # total admissions to date
        "screen_count": int(entry.get("scrnCnt", 0)),
        "showing_count": int(entry.get("showCnt", 0)),
    }


def _format_weekly_entry(entry: dict) -> dict:
    """Normalize a single weekly/weekend box office entry."""
    return {
        "rank": int(entry.get("rank", 0)),
        "rank_change": int(entry.get("rankInten", 0)),
        "is_new_entry": entry.get("rankOldAndNew") == "NEW",
        "movie_code": entry.get("movieCd"),
        "title": entry.get("movieNm"),
        "release_date": entry.get("openDt"),
        "sales_amount": int(entry.get("salesAmt", 0)),
        "sales_share": float(entry.get("salesShare", 0)),
        "sales_change": int(entry.get("salesInten", 0)),
        "sales_change_pct": float(entry.get("salesChange", 0)),
        "audience_count": int(entry.get("audiCnt", 0)),
        "audience_change": int(entry.get("audiInten", 0)),
        "audience_change_pct": float(entry.get("audiChange", 0)),
        "cumulative_audience": int(entry.get("audiAcc", 0)),
        "screen_count": int(entry.get("scrnCnt", 0)),
        "showing_count": int(entry.get("showCnt", 0)),
    }


# ── box office endpoints ──────────────────────────────────────────────────────

def get_daily_boxoffice(target_date: str = None) -> dict:
    """
    Get the Korean daily box office rankings for a specific date.

    Args:
        target_date: Date string in YYYYMMDD format.
                     Defaults to yesterday (most recent available).

    Returns:
        Dict with date, box_office_type, show_range, and rankings list.

    Note:
        KOBIS typically has data available from the previous day onward.
        Same-day data is not available.
    """
    if target_date is None:
        yesterday = date.today() - timedelta(days=1)
        target_date = yesterday.strftime("%Y%m%d")

    data = _get("/boxoffice/searchDailyBoxOfficeList.json", {
        "targetDt": target_date,
        "repNationCd": "K",   # K = Korean films only, blank = all films
    })

    result = data.get("boxOfficeResult", {})

    return {
        "date": target_date,
        "box_office_type": result.get("boxofficeType"),
        "show_range": result.get("showRange"),
        "rankings": [
            _format_daily_entry(e)
            for e in result.get("dailyBoxOfficeList", [])
        ]
    }


def get_weekly_boxoffice(target_date: str = None, weekend_only: bool = False) -> dict:
    """
    Get the Korean weekly or weekend box office rankings.

    Args:
        target_date:  Any date within the target week, YYYYMMDD format.
                      KOBIS uses the Monday of that week as the anchor.
                      Defaults to the most recently completed week.
        weekend_only: If True, returns Friday–Sunday rankings only.
                      If False, returns full Monday–Sunday weekly rankings.

    Returns:
        Dict with week range, type, and rankings list.
    """
    if target_date is None:
        # KOBIS weekly endpoint anchors on Sunday (end of week)
        last_sunday = _prev_weekday(date.today(), 6)
        target_date = last_sunday.strftime("%Y%m%d")

    # weekGb: "0" = weekly (Mon-Sun), "1" = weekend (Fri-Sun)
    week_gb = "1" if weekend_only else "0"

    data = _get("/boxoffice/searchWeeklyBoxOfficeList.json", {
        "targetDt": target_date,
        "weekGb": week_gb,
        "repNationCd": "K",
    })

    result = data.get("boxOfficeResult", {})
    period = "weekend" if weekend_only else "weekly"

    return {
        "period": period,
        "show_range": result.get("showRange"),
        "box_office_type": result.get("boxofficeType"),
        "rankings": [
            _format_weekly_entry(e)
            for e in result.get("weeklyBoxOfficeList", [])
        ]
    }


def get_all_films_boxoffice(target_date: str = None, weekend_only: bool = False) -> dict:
    """
    Get box office rankings including all films (Korean + foreign).
    Useful for showing Korean films' performance in context of the full market.

    Args:
        target_date:  Week anchor date in YYYYMMDD format. Defaults to last week.
        weekend_only: Weekend-only rankings if True.

    Returns:
        Same structure as get_weekly_boxoffice but includes foreign films.
    """
    if target_date is None:
        last_sunday = _prev_weekday(date.today(), 6)
        target_date = last_sunday.strftime("%Y%m%d")

    week_gb = "1" if weekend_only else "0"

    data = _get("/boxoffice/searchWeeklyBoxOfficeList.json", {
        "targetDt": target_date,
        "weekGb": week_gb,
        # No repNationCd = all nationalities
    })

    result = data.get("boxOfficeResult", {})

    return {
        "period": "weekend" if weekend_only else "weekly",
        "show_range": result.get("showRange"),
        "includes_foreign": True,
        "rankings": [
            _format_weekly_entry(e)
            for e in result.get("weeklyBoxOfficeList", [])
        ]
    }


# ── movie detail ──────────────────────────────────────────────────────────────

def get_movie_info(movie_code: str) -> dict:
    """
    Get detailed info for a specific movie using its KOBIS movie code.
    Movie codes appear in box office results as 'movie_code'.

    Args:
        movie_code: KOBIS movie code (e.g. "20240001")

    Returns:
        Dict with full movie metadata from KOBIS.
    """
    data = _get("/movie/searchMovieInfo.json", {"movieCd": movie_code})
    info = data.get("movieInfoResult", {}).get("movieInfo", {})

    if not info:
        return {"error": f"No movie found for code '{movie_code}'"}

    return {
        "movie_code": info.get("movieCd"),
        "title": info.get("movieNm"),
        "title_english": info.get("movieNmEn"),
        "title_original": info.get("movieNmOg"),
        "production_year": info.get("prdtYear"),
        "release_date": info.get("openDt"),
        "runtime_minutes": info.get("showTm"),
        "production_status": info.get("prdtStatNm"),
        "type": info.get("typeNm"),              # e.g. "장편" (feature), "단편" (short)
        "nations": [n.get("nationNm") for n in info.get("nations", [])],
        "genres": [g.get("genreNm") for g in info.get("genres", [])],
        "directors": [
            {"name": d.get("peopleNm"), "english_name": d.get("peopleNmEn")}
            for d in info.get("directors", [])
        ],
        "actors": [
            {
                "name": a.get("peopleNm"),
                "english_name": a.get("peopleNmEn"),
                "cast": a.get("cast"),
                "cast_english": a.get("castEn"),
            }
            for a in info.get("actors", [])
        ],
        "companies": [
            {"name": c.get("companyNm"), "type": c.get("companyPartNm")}
            for c in info.get("companys", [])
        ],
        "audits": [
            {"no": a.get("auditNo"), "rating": a.get("watchGradeNm")}
            for a in info.get("audits", [])
        ],
        "staffs": [
            {"name": s.get("peopleNm"), "role": s.get("staffRoleNm")}
            for s in info.get("staffs", [])
        ],
    }


def search_movies(
    title: str = None,
    director: str = None,
    actor: str = None,
    year: str = None,
    genre: str = None,
    page: int = 1,
    per_page: int = 10
) -> dict:
    """
    Search the KOBIS movie database.

    Args:
        title:     Movie title (Korean or English)
        director:  Director name
        actor:     Actor name
        year:      Production year (e.g. "2024")
        genre:     Genre name in Korean (e.g. "드라마", "액션", "로맨스")
        page:      Page number for pagination
        per_page:  Results per page (max 100)

    Returns:
        Dict with total count, page info, and list of movies.
    """
    params = {
        "curPage": page,
        "itemPerPage": per_page,
        # repNationCd omitted: uses numeric codes in movie list endpoint, causes 0 results
    }

    if title:
        params["movieNm"] = title
    if director:
        params["directorNm"] = director
    if actor:
        params["actorNm"] = actor
    if year:
        params["prdtStartYear"] = year
        params["prdtEndYear"] = year
    if genre:
        params["genreAlt"] = genre

    data = _get("/movie/searchMovieList.json", params)
    result = data.get("movieListResult", {})

    movies = [
        {
            "movie_code": m.get("movieCd"),
            "title": m.get("movieNm"),
            "title_english": m.get("movieNmEn"),
            "production_year": m.get("prdtYear"),
            "release_date": m.get("openDt"),
            "type": m.get("typeNm"),
            "nations": m.get("nationAlt", ""),
            "genres": m.get("genreAlt", ""),
            "directors": m.get("directors", []),
            "companies": m.get("companys", []),
        }
        for m in result.get("movieList", [])
    ]

    return {
        "total_count": int(result.get("totCnt", 0)),
        "page": page,
        "per_page": per_page,
        "movies": movies,
    }