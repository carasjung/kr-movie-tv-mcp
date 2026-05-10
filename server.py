"""
server.py — Korean Entertainment MCP Server

Exposes the Korean entertainment database as MCP tools for AI agents.
Built with FastMCP + Descope OAuth 2.1 auth.

Environment variables required:
    SUPABASE_URL
    SUPABASE_ANON_KEY
    SUPABASE_SERVICE_ROLE_KEY
    DESCOPE_WELL_KNOWN_URL
    MCP_SERVER_URL  (your Railway public URL e.g. https://kr-mcp.up.railway.app)

Tools:
  Discovery:  search_titles, get_trending_dramas, get_top_dramas,
              get_top_movies, browse_by_genre, browse_by_tag
  Detail:     get_movie, get_drama, get_cast, get_episode_ratings,
              get_ost_albums
  Utility:    find_where_to_watch, find_by_provider, get_weekly_boxoffice,
              get_actor_filmography, get_awards, compare_ratings
"""

import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.descope import DescopeProvider
from db.queries import (
    get_movie_by_tmdb_id,
    get_movie_by_title,
    get_movies,
    get_show_by_tmdb_id,
    get_show_by_title,
    get_shows,
    get_trending_shows,
    get_top_shows,
    get_movie_cast,
    get_show_cast,
    get_episodes,
    get_ost_albums,
    get_streaming_for_movie,
    get_streaming_for_show,
    get_titles_by_provider,
    get_weekly_boxoffice,
    get_boxoffice_history,
    get_awards_for_movie,
    get_awards_for_show,
    get_awards_by_ceremony,
    get_person_filmography,
    _supabase,
)

# Initialize Descope auth
_auth = DescopeProvider(
    config_url=os.environ["DESCOPE_WELL_KNOWN_URL"],
    base_url=os.environ["MCP_SERVER_URL"],
)

mcp = FastMCP(
    name="Korean Entertainment",
    auth=_auth,
    instructions="""
You have access to a comprehensive database of Korean movies and TV shows,
built from 10 sources: TMDB, KOBIS box office, MyDramaList, HanCinema,
Naver Movies, Naver TV (Nielsen Korea ratings), JustWatch, Wikipedia,
and Korean award ceremonies.

Rating fields and what they mean:
- tmdb_rating: Global community score (0-10)
- mdl_rating: International K-drama fan score (0-10)
- naver_audience_rating: Korean verified ticket buyers (0-10)
- naver_netizen_rating: Korean general public score (0-10)
- naver_latest_rating: Nielsen Korea latest episode viewership (%)
- naver_highest_rating: Nielsen Korea peak episode viewership (%)
- rt_tomatometer: Western professional critics (0-100%)
- rt_audience_score: Western RT users (0-100%)

Tips:
- For Korean drama recommendations, use mdl_rating and tags
- For films, use naver_audience_rating for Korean audience opinion
- For streaming, specify a region (us, uk, ca, au)
- Episode ratings show viewership trajectory (rising = building buzz)
""",
)


# ── Discovery Tools ────────────────────────────────────────────────────────────

@mcp.tool
def search_titles(
    query: str,
    content_type: str = "both",
    limit: int = 10,
) -> dict:
    """
    Search for Korean movies and/or TV shows by title.

    Args:
        query:        Title to search for (partial match supported)
        content_type: "movie", "drama", or "both" (default)
        limit:        Max results per type (default 10)

    Returns:
        Dict with "movies" and/or "shows" lists.
    """
    results = {}

    if content_type in ("movie", "both"):
        movies = _supabase.table("movies") \
            .select("id, tmdb_id, title_english, title_korean, release_year, "
                    "tmdb_rating, naver_audience_rating, genres, poster_url") \
            .ilike("title_english", f"%{query}%") \
            .order("tmdb_rating", desc=True) \
            .limit(limit) \
            .execute().data or []

        # Also search Korean titles
        if len(movies) < limit:
            kr_movies = _supabase.table("movies") \
                .select("id, tmdb_id, title_english, title_korean, release_year, "
                        "tmdb_rating, naver_audience_rating, genres, poster_url") \
                .ilike("title_korean", f"%{query}%") \
                .order("tmdb_rating", desc=True) \
                .limit(limit - len(movies)) \
                .execute().data or []
            seen_ids = {m["id"] for m in movies}
            movies += [m for m in kr_movies if m["id"] not in seen_ids]

        results["movies"] = movies

    if content_type in ("drama", "both"):
        shows = _supabase.table("tv_shows") \
            .select("id, tmdb_id, title_english, title_korean, year, status, "
                    "mdl_rating, tmdb_rating, total_episodes, genres, poster_url") \
            .ilike("title_english", f"%{query}%") \
            .order("mdl_rating", desc=True) \
            .limit(limit) \
            .execute().data or []

        if len(shows) < limit:
            kr_shows = _supabase.table("tv_shows") \
                .select("id, tmdb_id, title_english, title_korean, year, status, "
                        "mdl_rating, tmdb_rating, total_episodes, genres, poster_url") \
                .ilike("title_korean", f"%{query}%") \
                .order("mdl_rating", desc=True) \
                .limit(limit - len(shows)) \
                .execute().data or []
            seen_ids = {s["id"] for s in shows}
            shows += [s for s in kr_shows if s["id"] not in seen_ids]

        results["shows"] = shows

    total = sum(len(v) for v in results.values())
    results["total_found"] = total
    results["query"] = query
    return results


@mcp.tool
def get_trending_dramas(limit: int = 20) -> list[dict]:
    """
    Get currently airing Korean dramas sorted by MyDramaList rating.
    These are shows actively broadcasting right now.

    Args:
        limit: Number of results (default 20, max 50)

    Returns:
        List of airing dramas with ratings, episodes, and network.
    """
    limit = min(limit, 50)
    return _supabase.table("tv_shows") \
        .select("id, title_english, title_korean, year, network, total_episodes, "
                "mdl_rating, tmdb_rating, naver_latest_rating, naver_highest_rating, "
                "naver_latest_episode, genres, tags, poster_url, status") \
        .eq("status", "Airing") \
        .order("mdl_rating", desc=True) \
        .limit(limit) \
        .execute().data or []


@mcp.tool
def get_top_dramas(
    limit: int = 20,
    genre: str | None = None,
    min_rating: float = 8.0,
) -> list[dict]:
    """
    Get top-rated completed Korean dramas.

    Args:
        limit:      Number of results (default 20)
        genre:      Filter by genre e.g. "Romance", "Thriller", "Fantasy"
        min_rating: Minimum MDL rating (default 8.0)

    Returns:
        List of top dramas sorted by MDL rating descending.
    """
    query = _supabase.table("tv_shows") \
        .select("id, title_english, title_korean, year, network, total_episodes, "
                "mdl_rating, tmdb_rating, naver_highest_rating, "
                "genres, tags, poster_url, status") \
        .eq("status", "Ended") \
        .gte("mdl_rating", min_rating) \
        .order("mdl_rating", desc=True) \
        .limit(limit)

    if genre:
        query = query.contains("genres", [genre])

    return query.execute().data or []


@mcp.tool
def get_top_movies(
    limit: int = 20,
    genre: str | None = None,
    min_rating: float = 7.0,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict]:
    """
    Get top-rated Korean films.

    Args:
        limit:      Number of results (default 20)
        genre:      Filter by genre e.g. "Thriller", "Drama", "Horror"
        min_rating: Minimum TMDB rating (default 7.0)
        year_from:  Filter from this year onward
        year_to:    Filter up to this year

    Returns:
        List of top films sorted by TMDB rating descending.
    """
    query = _supabase.table("movies") \
        .select("id, title_english, title_korean, release_year, runtime_minutes, "
                "tmdb_rating, naver_audience_rating, naver_netizen_rating, "
                "rt_tomatometer, rt_audience_score, genres, poster_url") \
        .gte("tmdb_rating", min_rating) \
        .order("tmdb_rating", desc=True) \
        .limit(limit)

    if genre:
        query = query.contains("genres", [genre])
    if year_from:
        query = query.gte("release_year", year_from)
    if year_to:
        query = query.lte("release_year", year_to)

    return query.execute().data or []


@mcp.tool
def browse_by_genre(
    genre: str,
    content_type: str = "drama",
    limit: int = 20,
    status: str | None = None,
) -> list[dict]:
    """
    Browse Korean content by genre.

    Args:
        genre:        Genre name e.g. "Romance", "Thriller", "Fantasy",
                      "Historical", "Comedy", "Mystery", "Horror", "Action"
        content_type: "drama" or "movie" (default: drama)
        limit:        Number of results (default 20)
        status:       For dramas: "Airing", "Ended", or "Upcoming"

    Returns:
        List of titles matching the genre.
    """
    if content_type == "movie":
        query = _supabase.table("movies") \
            .select("id, title_english, title_korean, release_year, "
                    "tmdb_rating, naver_audience_rating, genres, poster_url") \
            .contains("genres", [genre]) \
            .order("tmdb_rating", desc=True) \
            .limit(limit)
        return query.execute().data or []
    else:
        query = _supabase.table("tv_shows") \
            .select("id, title_english, title_korean, year, status, "
                    "mdl_rating, tmdb_rating, genres, tags, total_episodes, poster_url") \
            .contains("genres", [genre]) \
            .order("mdl_rating", desc=True) \
            .limit(limit)
        if status:
            query = query.eq("status", status)
        return query.execute().data or []


@mcp.tool
def browse_by_tag(
    tag: str,
    limit: int = 20,
    min_rating: float | None = None,
) -> list[dict]:
    """
    Browse Korean dramas by MyDramaList community tag.
    Tags are community-generated and capture tropes, themes, and character types.

    Common tags: "Bromance", "Time Travel", "CEO Male Lead", "Found Family",
    "Age Gap", "Fake Relationship", "Enemies to Lovers", "Revenge",
    "Medical", "Legal", "School Life", "Supernatural", "Reincarnation"

    Args:
        tag:        MDL community tag to filter by
        limit:      Number of results (default 20)
        min_rating: Minimum MDL rating filter

    Returns:
        List of dramas with this tag, sorted by MDL rating.
    """
    query = _supabase.table("tv_shows") \
        .select("id, title_english, title_korean, year, status, "
                "mdl_rating, tmdb_rating, genres, tags, total_episodes, "
                "network, poster_url") \
        .contains("tags", [tag]) \
        .order("mdl_rating", desc=True) \
        .limit(limit)

    if min_rating:
        query = query.gte("mdl_rating", min_rating)

    return query.execute().data or []


# ── Detail Tools ───────────────────────────────────────────────────────────────

@mcp.tool
def get_movie(title: str, year: int | None = None) -> dict:
    """
    Get full details for a Korean film including all ratings and metadata.

    Args:
        title: English or Korean film title
        year:  Release year for disambiguation (recommended for common titles)

    Returns:
        Full movie record with all ratings, genres, synopsis, and source IDs.
        Returns {"found": False} if not found.
    """
    # Try exact then fuzzy match
    result = get_movie_by_title(title)
    if not result:
        # Try Korean title
        kr_result = _supabase.table("movies") \
            .select("*") \
            .ilike("title_korean", f"%{title}%") \
            .limit(1) \
            .execute().data
        result = kr_result[0] if kr_result else None

    if not result:
        return {"found": False, "title": title}

    # Disambiguate by year if multiple results and year provided
    if year and result.get("release_year") and abs(result["release_year"] - year) > 1:
        yr_result = _supabase.table("movies") \
            .select("*") \
            .ilike("title_english", f"%{title}%") \
            .eq("release_year", year) \
            .limit(1) \
            .execute().data
        if yr_result:
            result = yr_result[0]

    result["found"] = True
    return result


@mcp.tool
def get_drama(title: str, year: int | None = None) -> dict:
    """
    Get full details for a Korean TV drama including all ratings and metadata.

    Args:
        title: English or Korean drama title
        year:  Premiere year for disambiguation

    Returns:
        Full show record with all ratings, genres, tags, synopsis.
        Returns {"found": False} if not found.
    """
    result = get_show_by_title(title)
    if not result:
        kr_result = _supabase.table("tv_shows") \
            .select("*") \
            .ilike("title_korean", f"%{title}%") \
            .limit(1) \
            .execute().data
        result = kr_result[0] if kr_result else None

    if not result:
        return {"found": False, "title": title}

    if year and result.get("year") and abs(result["year"] - year) > 1:
        yr_result = _supabase.table("tv_shows") \
            .select("*") \
            .ilike("title_english", f"%{title}%") \
            .eq("year", year) \
            .limit(1) \
            .execute().data
        if yr_result:
            result = yr_result[0]

    result["found"] = True
    return result


@mcp.tool
def get_cast(title: str, content_type: str = "drama") -> dict:
    """
    Get the cast for a Korean movie or drama.

    Args:
        title:        English or Korean title
        content_type: "drama" or "movie"

    Returns:
        Dict with title info and cast list including character names and roles.
    """
    if content_type == "movie":
        title_row = get_movie_by_title(title)
        if not title_row:
            return {"found": False, "title": title}
        cast = get_movie_cast(title_row["id"])
        return {
            "found": True,
            "title": title_row["title_english"],
            "year": title_row.get("release_year"),
            "cast": cast,
        }
    else:
        title_row = get_show_by_title(title)
        if not title_row:
            return {"found": False, "title": title}
        cast = get_show_cast(title_row["id"])
        return {
            "found": True,
            "title": title_row["title_english"],
            "year": title_row.get("year"),
            "cast": cast,
        }


@mcp.tool
def get_episode_ratings(title: str) -> dict:
    """
    Get per-episode Nielsen Korea viewership ratings for a drama.
    Nielsen ratings are broadcast viewership percentages — 20%+ is a major hit.

    Args:
        title: English or Korean drama title

    Returns:
        Dict with show info, episode ratings list, and peak/latest stats.
        Ratings are percentages e.g. 20.5 means 20.5% of Korean TV households.
    """
    title_row = get_show_by_title(title)
    if not title_row:
        # Try Korean title
        kr = _supabase.table("tv_shows") \
            .select("id, title_english, title_korean, year, "
                    "naver_latest_rating, naver_highest_rating, naver_latest_episode") \
            .ilike("title_korean", f"%{title}%") \
            .limit(1) \
            .execute().data
        title_row = kr[0] if kr else None

    if not title_row:
        return {"found": False, "title": title}

    episodes = get_episodes(title_row["id"])

    return {
        "found": True,
        "title": title_row["title_english"],
        "title_korean": title_row.get("title_korean"),
        "year": title_row.get("year"),
        "naver_latest_rating": title_row.get("naver_latest_rating"),
        "naver_highest_rating": title_row.get("naver_highest_rating"),
        "naver_latest_episode": title_row.get("naver_latest_episode"),
        "episodes": episodes,
        "total_episodes_tracked": len(episodes),
        "note": "Nielsen Korea viewership %. 10%+ is solid, 20%+ is a major hit.",
    }


@mcp.tool
def get_ost_albums(title: str) -> dict:
    """
    Get OST (Original Soundtrack) albums for a Korean drama.
    Includes album names, artists, release dates, and Naver Vibe streaming links.

    Args:
        title: English or Korean drama title

    Returns:
        Dict with drama info and list of OST albums.
    """
    title_row = get_show_by_title(title)
    if not title_row:
        kr = _supabase.table("tv_shows") \
            .select("id, title_english, title_korean, year") \
            .ilike("title_korean", f"%{title}%") \
            .limit(1) \
            .execute().data
        title_row = kr[0] if kr else None

    if not title_row:
        return {"found": False, "title": title}

    albums = get_ost_albums(title_row["id"])
    return {
        "found": True,
        "title": title_row["title_english"],
        "year": title_row.get("year"),
        "ost_albums": albums,
        "total_albums": len(albums),
    }


# ── Utility Tools ──────────────────────────────────────────────────────────────

@mcp.tool
def find_where_to_watch(
    title: str,
    content_type: str = "drama",
    region: str = "us",
) -> dict:
    """
    Find streaming availability for a Korean movie or drama.

    Args:
        title:        English or Korean title
        content_type: "drama" or "movie"
        region:       "us", "uk", "ca", or "au" (default: "us")

    Returns:
        Dict with streaming options grouped by monetization type
        (Subscription, Rent, Buy, Free).
    """
    region = region.lower()
    if region not in ("us", "uk", "ca", "au"):
        return {"error": "Region must be one of: us, uk, ca, au"}

    if content_type == "movie":
        title_row = get_movie_by_title(title)
        if not title_row:
            return {"found": False, "title": title}
        offers = get_streaming_for_movie(title_row["id"], region=region)
        display_title = title_row["title_english"]
        year = title_row.get("release_year")
    else:
        title_row = get_show_by_title(title)
        if not title_row:
            return {"found": False, "title": title}
        offers = get_streaming_for_show(title_row["id"], region=region)
        display_title = title_row["title_english"]
        year = title_row.get("year")

    # Group by monetization type
    grouped: dict[str, list] = {}
    for offer in offers:
        mtype = offer.get("monetization_type") or "Other"
        if mtype not in grouped:
            grouped[mtype] = []
        grouped[mtype].append({
            "provider": offer["provider"],
            "quality": offer.get("quality"),
            "price": offer.get("price"),
            "watch_url": offer.get("watch_url"),
        })

    return {
        "found": True,
        "title": display_title,
        "year": year,
        "region": region.upper(),
        "streaming": grouped,
        "total_options": len(offers),
        "available": len(offers) > 0,
    }


@mcp.tool
def find_by_provider(
    provider: str,
    region: str = "us",
    content_type: str = "both",
    limit: int = 20,
) -> dict:
    """
    Find all Korean content available on a specific streaming provider.

    Args:
        provider:     Provider name e.g. "Netflix", "Viki", "Apple TV",
                      "Amazon Prime Video", "Kanopy", "Peacock"
        region:       "us", "uk", "ca", or "au" (default: "us")
        content_type: "movie", "drama", or "both"
        limit:        Max results per type

    Returns:
        Dict with movies and/or shows available on this provider.
    """
    region = region.lower()
    rows = _supabase.table("streaming_availability") \
        .select("*, movies(title_english, release_year, tmdb_rating, poster_url), "
                "tv_shows(title_english, year, mdl_rating, poster_url)") \
        .ilike("provider", f"%{provider}%") \
        .eq("region", region) \
        .eq("monetization_type", "Subscription") \
        .execute().data or []

    movies = []
    shows = []
    for row in rows:
        if row.get("movie_id") and row.get("movies") and content_type in ("movie", "both"):
            movies.append({**row["movies"], "watch_url": row.get("watch_url")})
        if row.get("show_id") and row.get("tv_shows") and content_type in ("drama", "both"):
            shows.append({**row["tv_shows"], "watch_url": row.get("watch_url")})

    # Deduplicate
    seen = set()
    unique_movies = []
    for m in movies:
        if m["title_english"] not in seen:
            seen.add(m["title_english"])
            unique_movies.append(m)

    seen = set()
    unique_shows = []
    for s in shows:
        if s["title_english"] not in seen:
            seen.add(s["title_english"])
            unique_shows.append(s)

    return {
        "provider": provider,
        "region": region.upper(),
        "movies": unique_movies[:limit],
        "shows": unique_shows[:limit],
        "total_movies": len(unique_movies),
        "total_shows": len(unique_shows),
    }


@mcp.tool
def get_weekly_boxoffice(week_start: str | None = None) -> dict:
    """
    Get Korean weekly box office rankings from KOBIS (official Korean Film Council).
    Returns the top 10 films with admissions, revenue, and market share.

    Args:
        week_start: Date in YYYY-MM-DD format (defaults to most recent week)

    Returns:
        Dict with rankings list and week metadata.
        audience_count = total Korean cinema admissions for that week.
        sales_share = percentage of total Korean box office.
    """
    rows = get_weekly_boxoffice(week_start=week_start, limit=10)
    if not rows:
        return {"found": False, "message": "No box office data available for this week."}

    return {
        "found": True,
        "week_start": rows[0].get("week_start") if rows else week_start,
        "rankings": [
            {
                "rank": r.get("rank"),
                "title": r.get("movies", {}).get("title_english") or r.get("kobis_movie_code"),
                "title_korean": r.get("movies", {}).get("title_korean"),
                "admissions_this_week": r.get("audience_count"),
                "revenue_krw": r.get("sales_amount"),
                "market_share_pct": r.get("sales_share"),
                "screens": r.get("screen_count"),
                "poster_url": r.get("movies", {}).get("poster_url"),
            }
            for r in rows
        ],
        "source": "KOBIS (Korean Film Council) — official theatrical data",
    }


@mcp.tool
def get_actor_filmography(name: str) -> dict:
    """
    Get the full filmography for a Korean actor or director.

    Args:
        name: Actor or director name (English or Korean)

    Returns:
        Dict with person info, movies list, and TV shows list.
    """
    # Search people table
    people = _supabase.table("people") \
        .select("*") \
        .or_(f"name_english.ilike.%{name}%,name_korean.ilike.%{name}%") \
        .limit(1) \
        .execute().data

    if not people:
        return {"found": False, "name": name}

    person = people[0]
    filmography = get_person_filmography(person["tmdb_person_id"])

    return {
        "found": True,
        "person": {
            "name_english": person.get("name_english"),
            "name_korean": person.get("name_korean"),
            "known_for": person.get("known_for_department"),
            "profile_url": person.get("profile_url"),
        },
        "movies": filmography.get("movies", []),
        "shows": filmography.get("shows", []),
        "total_movies": len(filmography.get("movies", [])),
        "total_shows": len(filmography.get("shows", [])),
    }


@mcp.tool
def get_awards(
    title: str | None = None,
    content_type: str = "drama",
    ceremony: str | None = None,
    year: int | None = None,
) -> dict:
    """
    Get award history for a title or browse a specific ceremony year.

    Use case 1 — awards for a title:
        get_awards(title="Goblin", content_type="drama")

    Use case 2 — browse a ceremony:
        get_awards(ceremony="Blue Dragon Film Awards", year=2024)

    Args:
        title:        Drama or film title (for title-based lookup)
        content_type: "drama" or "movie" (used with title)
        ceremony:     Ceremony name for ceremony-based lookup.
                      Options: "KBS Drama Awards", "MBC Drama Awards",
                      "SBS Drama Awards", "Blue Dragon Film Awards",
                      "Blue Dragon Series Awards", "Baeksang Arts Awards"
        year:         Year for ceremony-based lookup

    Returns:
        List of award records with categories, winners, and nominees.
    """
    if ceremony and year:
        awards = get_awards_by_ceremony(ceremony, year)
        return {
            "ceremony": ceremony,
            "year": year,
            "categories": awards,
            "total_categories": len(awards),
        }

    if title:
        if content_type == "movie":
            title_row = get_movie_by_title(title)
            if not title_row:
                return {"found": False, "title": title}
            awards = get_awards_for_movie(title_row["id"])
        else:
            title_row = get_show_by_title(title)
            if not title_row:
                return {"found": False, "title": title}
            awards = get_awards_for_show(title_row["id"])

        return {
            "found": True,
            "title": title_row.get("title_english"),
            "awards": awards,
            "total_wins": sum(1 for a in awards if a.get("won")),
            "total_nominations": len(awards),
        }

    return {"error": "Provide either a title or both ceremony and year."}


@mcp.tool
def compare_ratings(title: str, content_type: str = "drama") -> dict:
    """
    Compare ratings from different sources and audiences for a title.
    Useful for understanding the gap between Korean and international reception.

    Args:
        title:        English or Korean title
        content_type: "drama" or "movie"

    Returns:
        Structured rating comparison with context for each source.
    """
    if content_type == "movie":
        row = get_movie_by_title(title)
        if not row:
            return {"found": False, "title": title}

        return {
            "found": True,
            "title": row["title_english"],
            "year": row.get("release_year"),
            "ratings": {
                "korean_verified_buyers": {
                    "score": row.get("naver_audience_rating"),
                    "scale": "0-10",
                    "source": "Naver (실관람객)",
                    "audience": "Korean ticket buyers (verified purchase)",
                },
                "korean_public": {
                    "score": row.get("naver_netizen_rating"),
                    "scale": "0-10",
                    "source": "Naver (네티즌)",
                    "audience": "Korean general public",
                },
                "global_community": {
                    "score": row.get("tmdb_rating"),
                    "scale": "0-10",
                    "source": "TMDB",
                    "audience": "International community",
                },
                "western_critics": {
                    "score": row.get("rt_tomatometer"),
                    "scale": "0-100%",
                    "source": "Rotten Tomatoes",
                    "audience": "Western professional critics",
                },
                "western_audience": {
                    "score": row.get("rt_audience_score"),
                    "scale": "0-100%",
                    "source": "Rotten Tomatoes",
                    "audience": "Western RT users",
                },
            },
        }
    else:
        row = get_show_by_title(title)
        if not row:
            return {"found": False, "title": title}

        return {
            "found": True,
            "title": row["title_english"],
            "year": row.get("year"),
            "ratings": {
                "intl_kdrama_fans": {
                    "score": row.get("mdl_rating"),
                    "scale": "0-10",
                    "source": "MyDramaList",
                    "audience": "International K-drama community",
                },
                "global_community": {
                    "score": row.get("tmdb_rating"),
                    "scale": "0-10",
                    "source": "TMDB",
                    "audience": "International community",
                },
                "korean_tv_viewership": {
                    "latest_episode": row.get("naver_latest_rating"),
                    "peak_episode": row.get("naver_highest_rating"),
                    "scale": "% of Korean TV households",
                    "source": "Nielsen Korea via Naver",
                    "audience": "Korean broadcast viewers",
                    "note": "10%+ solid, 20%+ major hit, 30%+ legendary",
                },
            },
        }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
    )