"""
Tests for data_sources/mydramalist.py
Run from project root: PYTHONPATH=. python tests/test_mydramalist.py

Note: Each test opens a real browser — expect 5-10 seconds per test.
"""

from data_sources.mydramalist import (
    get_upcoming_dramas,
    get_popular_dramas,
    get_airing_dramas,
    get_top_dramas,
    get_drama_details,
)


def test_upcoming_dramas():
    print("\n=== Upcoming Korean Dramas ===")
    results = get_upcoming_dramas(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for show in results[:5]:
        print(f"  #{show['mdl_ranking']} {show['title']} "
              f"({show['year']}, {show['episode_count']} eps) "
              f"— ⭐ {show['rating'] or 'N/A'}")


def test_popular_dramas():
    print("\n=== Most Popular Korean Dramas ===")
    results = get_popular_dramas(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for show in results[:5]:
        print(f"  #{show['mdl_ranking']} {show['title']} "
              f"({show['year']}, {show['episode_count']} eps) "
              f"— ⭐ {show['rating'] or 'N/A'}")


def test_airing_dramas():
    print("\n=== Currently Airing Korean Dramas ===")
    results = get_airing_dramas(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for show in results[:5]:
        print(f"  #{show['mdl_ranking']} {show['title']} "
              f"({show['year']}, {show['episode_count']} eps) "
              f"— ⭐ {show['rating'] or 'N/A'}")


def test_top_dramas():
    print("\n=== Top Rated Korean Dramas ===")
    results = get_top_dramas(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for show in results[:5]:
        print(f"  #{show['mdl_ranking']} {show['title']} "
              f"({show['year']}, {show['episode_count']} eps) "
              f"— ⭐ {show['rating'] or 'N/A'}")


def test_drama_details():
    print("\n=== Drama Details: Goblin ===")
    result = get_drama_details("18452-goblin")
    print(f"  Title: {result['title']}")
    print(f"  Subtitle: {result.get('subtitle')}")
    print(f"  Native title: {result.get('native_title')}")
    print(f"  Rating: {result['rating']} ({result.get('votes')} votes)")
    print(f"  Synopsis: {str(result['synopsis'])[:150]}...")
    print(f"  Genres: {result.get('genres')}")
    print(f"  Tags: {result.get('tags')}")
    print(f"  Details: {result['details']}")
    for c in result["cast"][:5]:
        print(f"    {c['name']} as {c['character']} ({c['role_type']})")
    for w in result.get("where_to_watch", []):
        print(f"    {w['service']} - {w['type']}")


if __name__ == "__main__":
    test_upcoming_dramas()
    test_popular_dramas()
    test_airing_dramas()
    test_top_dramas()
    test_drama_details()
    print("\n All MDL tests complete.")