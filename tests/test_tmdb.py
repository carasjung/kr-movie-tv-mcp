"""
Tests for data_sources/tmdb.py
Run from project root: PYTHONPATH=. python tests/test_tmdb.py
"""

from data_sources.tmdb import (
    search_korean_content,
    get_movie_details,
    get_show_details,
    get_trending_korean,
    discover_korean_content,
    get_actor_filmography,
    get_recommendations,
    get_genres,
)


def test_search_korean_content():
    print("\n=== Search: Movies + TV (all) ===")
    result = search_korean_content("Parasite", content_type="all")
    print(f"Movies found: {result.get('movie_total_results', 0)}")
    for m in result.get("movies", [])[:2]:
        print(f"  [{m['type']}] {m['title']} ({m['original_title']}) — "
              f"⭐ {m['rating']} | {m['release_date']}")

    print("\n=== Search: TV only ===")
    result = search_korean_content("Crash Landing on You", content_type="tv")
    print(f"TV shows found: {result.get('tv_total_results', 0)}")
    for s in result.get("tv_shows", [])[:2]:
        print(f"  [{s['type']}] {s['title']} ({s['original_title']}) — "
              f"⭐ {s['rating']} | {s['first_air_date']}")


def test_get_movie_details():
    print("\n=== Movie Details: Parasite (496243) ===")
    result = get_movie_details(496243)  # Parasite / 기생충
    print(f"  Title: {result['title']} / {result['original_title']}")
    print(f"  Tagline: {result['tagline']}")
    print(f"  Runtime: {result['runtime_minutes']} min")
    print(f"  Rating: ⭐ {result['rating']} ({result['vote_count']:,} votes)")
    print(f"  Genres: {result['genres']}")
    print(f"  Status: {result['status']}")
    print(f"  Cast (top 3): {[c['name'] for c in result['cast'][:3]]}")
    print(f"  Director: {[c['name'] for c in result['crew'] if c['job'] == 'Director']}")
    print(f"  Keywords: {result['keywords'][:5]}")
    us_providers = result['watch_providers'].get('US', {})
    print(f"  Streaming (US): {us_providers.get('streaming', [])}")
    print(f"  Similar titles: {[m['title'] for m in result['similar'][:3]]}")


def test_get_show_details():
    print("\n=== Show Details: Crash Landing on You (94796) ===")
    result = get_show_details(94796)
    print(f"  Title: {result['title']} / {result['original_title']}")
    print(f"  Rating: ⭐ {result['rating']} ({result['vote_count']:,} votes)")
    print(f"  Episodes: {result['total_episodes']} | Seasons: {result['total_seasons']}")
    rt = result['episode_runtime']
    print(f"  Runtime per ep: {rt[0] if rt else 'N/A'} min")
    print(f"  Status: {result['status']}")
    print(f"  Networks: {result['networks']}")
    print(f"  Genres: {result['genres']}")
    print(f"  Cast (top 3): {[c['name'] for c in result['cast'][:3]]}")
    for s in result['seasons']:
        print(f"  Season {s['season_number']}: {s['episode_count']} eps ({s['air_date']})")
    us_providers = result['watch_providers'].get('US', {})
    print(f"  Streaming (US): {us_providers.get('streaming', [])}")


def test_get_trending_korean():
    print("\n=== Trending Korean This Week ===")
    result = get_trending_korean(content_type="all", time_window="week")
    print(f"Trending movies: {len(result.get('movies', []))}")
    for m in result.get("movies", [])[:3]:
        print(f"  🎬 {m['title']} — ⭐ {m['rating']} | {m['release_date']}")
    print(f"Trending TV: {len(result.get('tv_shows', []))}")
    for s in result.get("tv_shows", [])[:3]:
        print(f"  📺 {s['title']} — ⭐ {s['rating']} | {s['first_air_date']}")


def test_discover_korean_content():
    print("\n=== Discover: Top-rated Korean movies 2024 ===")
    result = discover_korean_content(
        content_type="movie",
        year=2024,
        min_rating=7.0,
        sort_by="vote_average.desc"
    )
    print(f"Total results: {result['total_results']} | Page {result['page']}/{result['total_pages']}")
    for m in result["results"][:5]:
        print(f"  {m['title']} — ⭐ {m['rating']}")

    print("\n=== Discover: Popular Korean TV shows ===")
    result = discover_korean_content(
        content_type="tv",
        sort_by="popularity.desc"
    )
    for s in result["results"][:5]:
        print(f"  {s['title']} — ⭐ {s['rating']} | {s['first_air_date']}")


def test_get_actor_filmography():
    print("\n=== Actor Filmography: Song Kang-ho ===")
    result = get_actor_filmography("Song Kang-ho")
    if "error" in result:
        print(f"  Error: {result['error']}")
        return
    print(f"  Name: {result['name']}")
    print(f"  Known for: {result['known_for_department']}")
    print(f"  Movies ({len(result['movies'])}):")
    for m in result["movies"][:5]:
        print(f"    {m['title']} ({m.get('release_date', 'N/A')[:4]}) — "
              f"as '{m.get('character', 'N/A')}'")
    print(f"  TV Shows ({len(result['tv_shows'])}):")
    for s in result["tv_shows"][:3]:
        print(f"    {s['title']} ({s.get('first_air_date', 'N/A')[:4]})")


def test_get_recommendations():
    print("\n=== Recommendations: Based on Parasite ===")
    results = get_recommendations(496243, content_type="movie")
    print(f"Recommendations: {len(results)}")
    for m in results[:5]:
        print(f"  {m['title']} — ⭐ {m['rating']}")

    print("\n=== Recommendations: Based on Crash Landing on You ===")
    results = get_recommendations(94796, content_type="tv")
    for s in results[:5]:
        print(f"  {s['title']} — ⭐ {s['rating']}")


def test_get_genres():
    print("\n=== Movie Genres ===")
    genres = get_genres("movie")
    print(f"  {genres}")

    print("\n=== TV Genres ===")
    genres = get_genres("tv")
    print(f"  {genres}")


if __name__ == "__main__":
    test_search_korean_content()
    test_get_movie_details()
    test_get_show_details()
    test_get_trending_korean()
    test_discover_korean_content()
    test_get_actor_filmography()
    test_get_recommendations()
    test_get_genres()
    print("\nAll TMDB tests complete.")