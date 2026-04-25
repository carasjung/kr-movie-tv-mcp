"""
TMDB API data source for Korean movies and TV shows.
Docs: https://developer.themoviedb.org/docs
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

# ── helpers ──────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = {}) -> dict:
    """Make a GET request to the TMDB API. Raises on HTTP errors."""
    if not TMDB_API_KEY:
        raise ValueError("TMDB_API_KEY is not set in your .env file.")
    
    response = requests.get(
        f"{BASE_URL}{endpoint}",
        params={"api_key": TMDB_API_KEY, "language": "en-US", **params},
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def _format_movie(movie: dict) -> dict:
    """Normalize a raw TMDB movie result into a clean dict."""
    return {
        "id": movie.get("id"),
        "title": movie.get("title"),
        "original_title": movie.get("original_title"),
        "type": "movie",
        "overview": movie.get("overview"),
        "release_date": movie.get("release_date"),
        "rating": movie.get("vote_average"),
        "vote_count": movie.get("vote_count"),
        "popularity": movie.get("popularity"),
        "genres": movie.get("genre_ids", []),
        "poster_url": f"{IMAGE_BASE_URL}{movie['poster_path']}" if movie.get("poster_path") else None,
        "original_language": movie.get("original_language"),
    }


def _format_show(show: dict) -> dict:
    """Normalize a raw TMDB TV result into a clean dict."""
    return {
        "id": show.get("id"),
        "title": show.get("name"),
        "original_title": show.get("original_name"),
        "type": "tv",
        "overview": show.get("overview"),
        "first_air_date": show.get("first_air_date"),
        "rating": show.get("vote_average"),
        "vote_count": show.get("vote_count"),
        "popularity": show.get("popularity"),
        "genres": show.get("genre_ids", []),
        "poster_url": f"{IMAGE_BASE_URL}{show['poster_path']}" if show.get("poster_path") else None,
        "original_language": show.get("original_language"),
    }


# ── search ────────────────────────────────────────────────────────────────────

def search_korean_content(query: str, content_type: str = "all", page: int = 1) -> dict:
    """
    Search for Korean movies and/or TV shows by title.

    Args:
        query:        Search term (title or keyword)
        content_type: "movie", "tv", or "all"
        page:         Page number for pagination (default 1)

    Returns:
        Dict with 'movies' and/or 'tv_shows' lists and pagination info.
    """
    results = {"query": query, "page": page}

    if content_type in ("movie", "all"):
        data = _get("/search/movie", {"query": query, "page": page, "region": "KR"})
        results["movies"] = [_format_movie(m) for m in data.get("results", [])]
        results["movie_total_results"] = data.get("total_results", 0)

    if content_type in ("tv", "all"):
        data = _get("/search/tv", {"query": query, "page": page})
        # Filter to Korean-language results when searching all
        shows = data.get("results", [])
        if content_type == "all":
            shows = [s for s in shows if s.get("original_language") == "ko"]
        results["tv_shows"] = [_format_show(s) for s in shows]
        results["tv_total_results"] = data.get("total_results", 0)

    return results


# ── details ───────────────────────────────────────────────────────────────────

def get_movie_details(tmdb_id: int) -> dict:
    """
    Get full details for a movie including cast, crew, and streaming availability.

    Args:
        tmdb_id: TMDB movie ID

    Returns:
        Dict with full movie metadata, cast, crew, and watch providers.
    """
    data = _get(f"/movie/{tmdb_id}", {
        "append_to_response": "credits,watch/providers,similar,keywords"
    })

    cast = [
        {
            "name": c["name"],
            "character": c.get("character"),
            "korean_name": c.get("original_name"),
            "profile_url": f"{IMAGE_BASE_URL}{c['profile_path']}" if c.get("profile_path") else None,
        }
        for c in data.get("credits", {}).get("cast", [])[:15]  # top 15
    ]

    crew = [
        {"name": c["name"], "job": c["job"]}
        for c in data.get("credits", {}).get("crew", [])
        if c.get("job") in ("Director", "Screenplay", "Writer", "Producer")
    ]

    # Streaming providers (US by default — most useful for international users)
    providers_raw = data.get("watch/providers", {}).get("results", {})
    watch_providers = {}
    for region, info in providers_raw.items():
        watch_providers[region] = {
            "streaming": [p["provider_name"] for p in info.get("flatrate", [])],
            "rent": [p["provider_name"] for p in info.get("rent", [])],
            "buy": [p["provider_name"] for p in info.get("buy", [])],
        }

    similar = [_format_movie(m) for m in data.get("similar", {}).get("results", [])[:5]]

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "original_title": data.get("original_title"),
        "type": "movie",
        "tagline": data.get("tagline"),
        "overview": data.get("overview"),
        "release_date": data.get("release_date"),
        "runtime_minutes": data.get("runtime"),
        "rating": data.get("vote_average"),
        "vote_count": data.get("vote_count"),
        "genres": [g["name"] for g in data.get("genres", [])],
        "poster_url": f"{IMAGE_BASE_URL}{data['poster_path']}" if data.get("poster_path") else None,
        "status": data.get("status"),
        "budget": data.get("budget"),
        "revenue": data.get("revenue"),
        "cast": cast,
        "crew": crew,
        "watch_providers": watch_providers,
        "similar": similar,
        "keywords": [k["name"] for k in data.get("keywords", {}).get("keywords", [])],
    }


def get_show_details(tmdb_id: int) -> dict:
    """
    Get full details for a TV show including cast, seasons, and streaming availability.

    Args:
        tmdb_id: TMDB TV show ID

    Returns:
        Dict with full show metadata, cast, seasons, and watch providers.
    """
    data = _get(f"/tv/{tmdb_id}", {
        "append_to_response": "credits,watch/providers,similar,keywords"
    })

    cast = [
        {
            "name": c["name"],
            "character": c.get("character"),
            "korean_name": c.get("original_name"),
            "profile_url": f"{IMAGE_BASE_URL}{c['profile_path']}" if c.get("profile_path") else None,
        }
        for c in data.get("credits", {}).get("cast", [])[:15]
    ]

    seasons = [
        {
            "season_number": s.get("season_number"),
            "episode_count": s.get("episode_count"),
            "air_date": s.get("air_date"),
            "name": s.get("name"),
        }
        for s in data.get("seasons", [])
        if s.get("season_number", 0) > 0  # exclude specials (season 0)
    ]

    providers_raw = data.get("watch/providers", {}).get("results", {})
    watch_providers = {}
    for region, info in providers_raw.items():
        watch_providers[region] = {
            "streaming": [p["provider_name"] for p in info.get("flatrate", [])],
            "rent": [p["provider_name"] for p in info.get("rent", [])],
            "buy": [p["provider_name"] for p in info.get("buy", [])],
        }

    similar = [_format_show(s) for s in data.get("similar", {}).get("results", [])[:5]]

    return {
        "id": data.get("id"),
        "title": data.get("name"),
        "original_title": data.get("original_name"),
        "type": "tv",
        "tagline": data.get("tagline"),
        "overview": data.get("overview"),
        "first_air_date": data.get("first_air_date"),
        "last_air_date": data.get("last_air_date"),
        "status": data.get("status"),
        "total_episodes": data.get("number_of_episodes"),
        "total_seasons": data.get("number_of_seasons"),
        "episode_runtime": data.get("episode_run_time", []) or None,
        "rating": data.get("vote_average"),
        "vote_count": data.get("vote_count"),
        "genres": [g["name"] for g in data.get("genres", [])],
        "networks": [n["name"] for n in data.get("networks", [])],
        "poster_url": f"{IMAGE_BASE_URL}{data['poster_path']}" if data.get("poster_path") else None,
        "cast": cast,
        "seasons": seasons,
        "watch_providers": watch_providers,
        "similar": similar,
        "keywords": [k["name"] for k in data.get("keywords", {}).get("results", [])],
    }


# ── trending & discovery ──────────────────────────────────────────────────────

def get_trending_korean(content_type: str = "all", time_window: str = "week") -> dict:
    """
    Get trending Korean movies and/or TV shows.

    Args:
        content_type: "movie", "tv", or "all"
        time_window:  "day" or "week"

    Returns:
        Dict with trending movies and/or tv_shows lists.
    """
    results = {}

    def _fetch_trending(media_type: str) -> list:
        # Fetch 2 pages to increase chances of finding Korean content
        items = []
        for page in (1, 2):
            data = _get(f"/trending/{media_type}/{time_window}", {"page": page})
            items.extend(data.get("results", []))
        return [r for r in items if r.get("original_language") == "ko"]

    if content_type in ("movie", "all"):
        raw = _fetch_trending("movie")
        results["movies"] = [_format_movie(m) for m in raw]

    if content_type in ("tv", "all"):
        raw = _fetch_trending("tv")
        results["tv_shows"] = [_format_show(s) for s in raw]

    results["time_window"] = time_window
    return results


def discover_korean_content(
    content_type: str = "movie",
    genre_ids: list[int] = None,
    year: int = None,
    min_rating: float = None,
    sort_by: str = "popularity.desc",
    page: int = 1
) -> dict:
    """
    Discover Korean content with filters.

    Args:
        content_type: "movie" or "tv"
        genre_ids:    List of TMDB genre IDs to filter by
        year:         Release year filter
        min_rating:   Minimum average rating (0-10)
        sort_by:      Sort order — "popularity.desc", "vote_average.desc",
                      "release_date.desc", "revenue.desc"
        page:         Page number

    Returns:
        Dict with results list and pagination info.
    """
    params = {
        "with_original_language": "ko",
        "sort_by": sort_by,
        "page": page,
    }

    if genre_ids:
        params["with_genres"] = ",".join(str(g) for g in genre_ids)
    if min_rating:
        params["vote_average.gte"] = min_rating
        params["vote_count.gte"] = 50  # avoid obscure titles with inflated scores

    if content_type == "movie":
        if year:
            params["primary_release_year"] = year
        data = _get("/discover/movie", params)
        items = [_format_movie(m) for m in data.get("results", [])]
    else:
        if year:
            params["first_air_date_year"] = year
        data = _get("/discover/tv", params)
        items = [_format_show(s) for s in data.get("results", [])]

    return {
        "content_type": content_type,
        "results": items,
        "page": data.get("page"),
        "total_pages": data.get("total_pages"),
        "total_results": data.get("total_results"),
    }


# ── person / actor ────────────────────────────────────────────────────────────

def get_actor_filmography(name: str) -> dict:
    """
    Search for a Korean actor/director and return their filmography.

    Args:
        name: Actor or director name (English or Korean)

    Returns:
        Dict with person info and their movie/TV credits.
    """
    # Search for the person
    search = _get("/search/person", {"query": name})
    results = search.get("results", [])

    if not results:
        return {"error": f"No person found for '{name}'"}

    person = results[0]  # take top result
    person_id = person["id"]

    # Get full credits
    credits = _get(f"/person/{person_id}/combined_credits")

    movies = [
        _format_movie(c) | {"character": c.get("character"), "order": c.get("order")}
        for c in credits.get("cast", [])
        if c.get("media_type") == "movie"
    ]
    tv_shows = [
        _format_show(c) | {"character": c.get("character"), "episode_count": c.get("episode_count")}
        for c in credits.get("cast", [])
        if c.get("media_type") == "tv"
    ]

    # Sort by release date descending
    movies.sort(key=lambda x: x.get("release_date") or "", reverse=True)
    tv_shows.sort(key=lambda x: x.get("first_air_date") or "", reverse=True)

    return {
        "id": person_id,
        "name": person.get("name"),
        "known_for_department": person.get("known_for_department"),
        "profile_url": f"{IMAGE_BASE_URL}{person['profile_path']}" if person.get("profile_path") else None,
        "movies": movies,
        "tv_shows": tv_shows,
    }


# ── recommendations ───────────────────────────────────────────────────────────

def get_recommendations(tmdb_id: int, content_type: str = "movie") -> list:
    """
    Get TMDB recommendations for a given movie or TV show.

    Args:
        tmdb_id:      TMDB ID of the source title
        content_type: "movie" or "tv"

    Returns:
        List of recommended titles.
    """
    data = _get(f"/{content_type}/{tmdb_id}/recommendations")
    results = data.get("results", [])

    if content_type == "movie":
        return [_format_movie(m) for m in results]
    else:
        return [_format_show(s) for s in results]


# ── genre reference ───────────────────────────────────────────────────────────

def get_genres(content_type: str = "movie") -> list:
    """
    Get the list of TMDB genre IDs and names (useful for discover filters).

    Args:
        content_type: "movie" or "tv"

    Returns:
        List of {"id": int, "name": str} dicts.
    """
    data = _get(f"/genre/{content_type}/list")
    return data.get("genres", [])