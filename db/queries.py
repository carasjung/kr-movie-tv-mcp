"""
db/queries.py — All database read and write operations.

This is the only file that talks to Supabase directly.
Pipeline jobs call upsert_* functions to write data.
The MCP server calls get_* functions to read data.

All writes use upsert (insert or update on conflict) so the
nightly pipeline can safely re-run without creating duplicates.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Use service role key for writes (bypasses RLS)
# Use anon key for reads in production MCP server
_supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _clean(data: dict) -> dict:
    """Remove None values from a dict before upserting."""
    return {k: v for k, v in data.items() if v is not None}


# ── movies ────────────────────────────────────────────────────────────────────

def upsert_movie(data: dict) -> dict:
    """
    Insert or update a movie record.
    Conflicts on tmdb_id — updates all other fields.

    Args:
        data: Dict matching MOVIE_FIELDS from models.py

    Returns:
        The upserted row as a dict.
    """
    result = _supabase.table("movies").upsert(
        _clean(data),
        on_conflict="tmdb_id"
    ).execute()
    return result.data[0] if result.data else {}


def get_movie_by_tmdb_id(tmdb_id: str) -> dict | None:
    """Get a movie by its TMDB ID."""
    result = _supabase.table("movies") \
        .select("*") \
        .eq("tmdb_id", tmdb_id) \
        .single() \
        .execute()
    return result.data


def get_movie_by_title(title: str) -> dict | None:
    """Search movies by English title (case-insensitive partial match)."""
    result = _supabase.table("movies") \
        .select("*") \
        .ilike("title_english", f"%{title}%") \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


def get_movies(
    genre: str = None,
    year: int = None,
    min_tmdb_rating: float = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Query movies with optional filters.

    Args:
        genre:            Filter by genre (e.g. "Thriller")
        year:             Filter by release year
        min_tmdb_rating:  Minimum TMDB rating
        limit:            Results per page
        offset:           Pagination offset

    Returns:
        List of movie dicts.
    """
    query = _supabase.table("movies").select("*")

    if genre:
        query = query.contains("genres", [genre])
    if year:
        query = query.eq("release_year", year)
    if min_tmdb_rating:
        query = query.gte("tmdb_rating", min_tmdb_rating)

    query = query.order("tmdb_rating", desc=True) \
                 .range(offset, offset + limit - 1)

    return query.execute().data or []


# ── tv shows ──────────────────────────────────────────────────────────────────

def upsert_show(data: dict) -> dict:
    """
    Insert or update a TV show record.
    Conflicts on tmdb_id — updates all other fields.

    Args:
        data: Dict matching SHOW_FIELDS from models.py

    Returns:
        The upserted row as a dict.
    """
    result = _supabase.table("tv_shows").upsert(
        _clean(data),
        on_conflict="tmdb_id"
    ).execute()
    return result.data[0] if result.data else {}


def get_show_by_tmdb_id(tmdb_id: str) -> dict | None:
    """Get a TV show by its TMDB ID."""
    result = _supabase.table("tv_shows") \
        .select("*") \
        .eq("tmdb_id", str(tmdb_id)) \
        .single() \
        .execute()
    return result.data


def get_show_by_mdl_id(mdl_id: str) -> dict | None:
    """Get a TV show by its MDL ID."""
    result = _supabase.table("tv_shows") \
        .select("*") \
        .eq("mdl_id", str(mdl_id)) \
        .single() \
        .execute()
    return result.data


def get_show_by_title(title: str) -> dict | None:
    """Search shows by English title (case-insensitive partial match)."""
    result = _supabase.table("tv_shows") \
        .select("*") \
        .ilike("title_english", f"%{title}%") \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


def get_shows(
    status: str = None,
    genre: str = None,
    tag: str = None,
    network: str = None,
    year: int = None,
    min_mdl_rating: float = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Query TV shows with optional filters.

    Args:
        status:          "Airing", "Ended", or "Upcoming"
        genre:           Filter by genre
        tag:             Filter by MDL community tag
        network:         Filter by network (e.g. "tvN", "Netflix")
        year:            Filter by premiere year
        min_mdl_rating:  Minimum MDL rating
        limit:           Results per page
        offset:          Pagination offset

    Returns:
        List of show dicts.
    """
    query = _supabase.table("tv_shows").select("*")

    if status:
        query = query.eq("status", status)
    if genre:
        query = query.contains("genres", [genre])
    if tag:
        query = query.contains("tags", [tag])
    if network:
        query = query.ilike("network", f"%{network}%")
    if year:
        query = query.eq("year", year)
    if min_mdl_rating:
        query = query.gte("mdl_rating", min_mdl_rating)

    query = query.order("mdl_rating", desc=True) \
                 .range(offset, offset + limit - 1)

    return query.execute().data or []


def get_trending_shows(limit: int = 20) -> list[dict]:
    """Get currently airing shows sorted by MDL rating."""
    return _supabase.table("tv_shows") \
        .select("*") \
        .eq("status", "Airing") \
        .order("mdl_rating", desc=True) \
        .limit(limit) \
        .execute().data or []


def get_top_shows(limit: int = 20) -> list[dict]:
    """Get top-rated completed shows sorted by MDL rating."""
    return _supabase.table("tv_shows") \
        .select("*") \
        .eq("status", "Ended") \
        .order("mdl_rating", desc=True) \
        .limit(limit) \
        .execute().data or []


# ── people & cast ─────────────────────────────────────────────────────────────

def upsert_person(data: dict) -> dict:
    """Insert or update a person record. Conflicts on tmdb_person_id."""
    result = _supabase.table("people").upsert(
        _clean(data),
        on_conflict="tmdb_person_id"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_movie_cast(movie_id: str, person_id: str, data: dict) -> dict:
    """Insert or update a movie cast relationship."""
    result = _supabase.table("movie_cast").upsert(
        {"movie_id": movie_id, "person_id": person_id, **_clean(data)},
        on_conflict="movie_id,person_id,role_type"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_show_cast(show_id: str, person_id: str, data: dict) -> dict:
    """Insert or update a show cast relationship."""
    result = _supabase.table("show_cast").upsert(
        {"show_id": show_id, "person_id": person_id, **_clean(data)},
        on_conflict="show_id,person_id,role_type"
    ).execute()
    return result.data[0] if result.data else {}


def get_movie_cast(movie_id: str) -> list[dict]:
    """Get full cast for a movie, joined with people data."""
    return _supabase.table("movie_cast") \
        .select("*, people(*)") \
        .eq("movie_id", movie_id) \
        .order("cast_order") \
        .execute().data or []


def get_show_cast(show_id: str) -> list[dict]:
    """Get full cast for a show, joined with people data."""
    return _supabase.table("show_cast") \
        .select("*, people(*)") \
        .eq("show_id", show_id) \
        .order("cast_order") \
        .execute().data or []


def get_person_filmography(tmdb_person_id: str) -> dict:
    """Get all movies and shows for a person."""
    person = _supabase.table("people") \
        .select("*") \
        .eq("tmdb_person_id", str(tmdb_person_id)) \
        .single() \
        .execute().data

    if not person:
        return {}

    movies = _supabase.table("movie_cast") \
        .select("*, movies(title_english, release_year, tmdb_rating, poster_url)") \
        .eq("person_id", person["id"]) \
        .execute().data or []

    shows = _supabase.table("show_cast") \
        .select("*, tv_shows(title_english, year, mdl_rating, poster_url)") \
        .eq("person_id", person["id"]) \
        .execute().data or []

    return {
        "person": person,
        "movies": movies,
        "shows": shows,
    }


# ── episodes ──────────────────────────────────────────────────────────────────

def upsert_episode(show_id: str, data: dict) -> dict:
    """Insert or update an episode rating. Conflicts on show_id + episode_number."""
    result = _supabase.table("episodes").upsert(
        {"show_id": show_id, **_clean(data)},
        on_conflict="show_id,episode_number"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_episodes_bulk(show_id: str, episodes: list[dict]) -> list[dict]:
    """Bulk upsert all episode ratings for a show."""
    rows = [{"show_id": show_id, **_clean(ep)} for ep in episodes]
    result = _supabase.table("episodes").upsert(
        rows,
        on_conflict="show_id,episode_number"
    ).execute()
    return result.data or []


def get_episodes(show_id: str) -> list[dict]:
    """Get all episode ratings for a show, ordered by episode number."""
    return _supabase.table("episodes") \
        .select("*") \
        .eq("show_id", show_id) \
        .order("episode_number") \
        .execute().data or []


# ── streaming availability ────────────────────────────────────────────────────

def upsert_streaming(data: dict) -> dict:
    """
    Insert or update a streaming availability record.
    Conflicts on movie_id/show_id + region + provider + monetization_type.
    """
    result = _supabase.table("streaming_availability").upsert(
        _clean(data),
        on_conflict="movie_id,show_id,region,provider,monetization_type"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_streaming_bulk(rows: list[dict]) -> list[dict]:
    """Bulk upsert streaming availability rows."""
    result = _supabase.table("streaming_availability").upsert(
        [_clean(r) for r in rows],
        on_conflict="movie_id,show_id,region,provider,monetization_type"
    ).execute()
    return result.data or []


def get_streaming_for_movie(movie_id: str, region: str = None) -> list[dict]:
    """Get streaming availability for a movie, optionally filtered by region."""
    query = _supabase.table("streaming_availability") \
        .select("*") \
        .eq("movie_id", movie_id)
    if region:
        query = query.eq("region", region)
    return query.order("monetization_type").execute().data or []


def get_streaming_for_show(show_id: str, region: str = None) -> list[dict]:
    """Get streaming availability for a show, optionally filtered by region."""
    query = _supabase.table("streaming_availability") \
        .select("*") \
        .eq("show_id", show_id)
    if region:
        query = query.eq("region", region)
    return query.order("monetization_type").execute().data or []


def get_titles_by_provider(provider: str, region: str = "us") -> dict:
    """Get all movies and shows available on a specific provider in a region."""
    rows = _supabase.table("streaming_availability") \
        .select("*, movies(title_english, release_year), tv_shows(title_english, year)") \
        .eq("provider", provider) \
        .eq("region", region) \
        .eq("monetization_type", "Subscription") \
        .execute().data or []

    movies = [r for r in rows if r.get("movie_id")]
    shows = [r for r in rows if r.get("show_id")]
    return {"provider": provider, "region": region, "movies": movies, "shows": shows}


# ── ost albums ────────────────────────────────────────────────────────────────

def upsert_ost_album(show_id: str, data: dict) -> dict:
    """Insert or update an OST album record."""
    result = _supabase.table("ost_albums").upsert(
        {"show_id": show_id, **_clean(data)},
        on_conflict="show_id,album_name"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_ost_albums_bulk(show_id: str, albums: list[dict]) -> list[dict]:
    """Bulk upsert all OST albums for a show."""
    rows = [{"show_id": show_id, **_clean(a)} for a in albums]
    result = _supabase.table("ost_albums").upsert(
        rows,
        on_conflict="show_id,album_name"
    ).execute()
    return result.data or []


def get_ost_albums(show_id: str) -> list[dict]:
    """Get all OST albums for a show."""
    return _supabase.table("ost_albums") \
        .select("*") \
        .eq("show_id", show_id) \
        .order("release_date") \
        .execute().data or []


# ── awards ────────────────────────────────────────────────────────────────────

def upsert_award(data: dict) -> dict:
    """Insert or update an award record."""
    result = _supabase.table("awards").upsert(
        _clean(data),
        on_conflict="ceremony,year,category,winner_name"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_award_nominees_bulk(award_id: str, nominees: list[dict]) -> list[dict]:
    """Bulk insert nominees for an award category."""
    rows = [{"award_id": award_id, **_clean(n)} for n in nominees]
    if not rows:
        return []
    result = _supabase.table("award_nominees").upsert(
        rows,
        on_conflict="award_id,nominee_name,nominee_show"
    ).execute()
    return result.data or []


def get_awards_for_movie(movie_id: str) -> list[dict]:
    """Get all awards and nominations for a movie."""
    return _supabase.table("awards") \
        .select("*, award_nominees(*)") \
        .eq("movie_id", movie_id) \
        .order("year", desc=True) \
        .execute().data or []


def get_awards_for_show(show_id: str) -> list[dict]:
    """Get all awards and nominations for a show."""
    return _supabase.table("awards") \
        .select("*, award_nominees(*)") \
        .eq("show_id", show_id) \
        .order("year", desc=True) \
        .execute().data or []


def get_awards_by_ceremony(ceremony: str, year: int) -> list[dict]:
    """Get all award categories for a specific ceremony and year."""
    return _supabase.table("awards") \
        .select("*, award_nominees(*)") \
        .eq("ceremony", ceremony) \
        .eq("year", year) \
        .order("category") \
        .execute().data or []


# ── box office ────────────────────────────────────────────────────────────────

def upsert_boxoffice(data: dict) -> dict:
    """Insert or update a box office record."""
    result = _supabase.table("boxoffice").upsert(
        _clean(data),
        on_conflict="kobis_movie_code,week_start,period_type"
    ).execute()
    return result.data[0] if result.data else {}


def upsert_boxoffice_bulk(rows: list[dict]) -> list[dict]:
    """Bulk upsert box office records."""
    result = _supabase.table("boxoffice").upsert(
        [_clean(r) for r in rows],
        on_conflict="kobis_movie_code,week_start,period_type"
    ).execute()
    return result.data or []


def get_weekly_boxoffice(week_start: str = None, limit: int = 10) -> list[dict]:
    """
    Get weekly Korean box office rankings.

    Args:
        week_start: Date string YYYY-MM-DD. Defaults to most recent week.
        limit:      Number of rankings to return.

    Returns:
        List of box office rows joined with movie titles.
    """
    query = _supabase.table("boxoffice") \
        .select("*, movies(title_english, title_korean, poster_url)") \
        .eq("period_type", "weekly")

    if week_start:
        query = query.eq("week_start", week_start)
    else:
        query = query.order("week_start", desc=True)

    return query.order("rank").limit(limit).execute().data or []


def get_boxoffice_history(movie_id: str) -> list[dict]:
    """Get full box office history for a specific movie."""
    return _supabase.table("boxoffice") \
        .select("*") \
        .eq("movie_id", movie_id) \
        .order("week_start") \
        .execute().data or []