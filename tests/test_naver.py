"""
Tests for data_sources/naver.py
Run from project root: PYTHONPATH=. python tests/test_naver.py

Note: Naver Movies covers Korean FILMS only — not TV dramas.
Each test opens a real browser — expect 10-15 seconds per test.
"""

from data_sources.naver import (
    search_movie,
    get_movie_ratings,
)


def test_search_current_film():
    print("\n=== Current Film: 살목지 ===")
    result = search_movie("살목지")
    if not result.get("found"):
        print("  Not found")
        return
    print(f"  Korean title: {result['korean_title']}")
    print(f"  English title: {result['english_title']}")
    print(f"  Year: {result['year']}")
    print(f"  Status: {result['status']}")
    print(f"  Genre: {result['genre']}")
    print(f"  Country: {result.get('country')}")
    print(f"  Runtime: {result['runtime_minutes']} min")
    print(f"  Release date: {result['release_date']}")
    print(f"  Synopsis: {str(result['synopsis'])[:150]}...")
    print(f"  Box office rank: #{result['box_office_rank']}")
    print(f"  Cumulative audience: {result['cumulative_audience']}")
    print(f"  Audience rating (silgwanlam): {result['audience_rating']}")
    print(f"  Netizen rating (netizen): {result['netizen_rating']}")
    print(f"  Cast:")
    for c in result["cast"][:5]:
        role_label = "director" if c["is_director"] else c["role"]
        print(f"    {c['name']} - {role_label}")
    print(f"  Recommendations: {result['recommendations'][:5]}")


def test_search_older_film():
    print("\n=== Older Film: Parasite ===")
    result = search_movie("기생충")
    if not result.get("found"):
        print("  Not found")
        return
    print(f"  Korean title: {result['korean_title']}")
    print(f"  English title: {result['english_title']}")
    print(f"  Year: {result['year']}")
    print(f"  Genre: {result['genre']}")
    print(f"  Country: {result.get('country')}")
    print(f"  Runtime: {result['runtime_minutes']} min")
    print(f"  Audience rating: {result['audience_rating']}")
    print(f"  Netizen rating: {result['netizen_rating']}")
    print(f"  Cast (top 3): {[c['name'] for c in result['cast'][:3]]}")


def test_get_ratings():
    print("\n=== Quick Rating Lookup: Salmokji ===")
    result = get_movie_ratings("살목지")
    print(f"  Title: {result['title']}")
    print(f"  Audience rating: {result['audience_rating']}")
    print(f"  Netizen rating: {result['netizen_rating']}")
    print(f"  Box office rank: #{result['box_office_rank']}")
    print(f"  Cumulative audience: {result['cumulative_audience']}")


if __name__ == "__main__":
    test_search_current_film()
    test_search_older_film()
    test_get_ratings()
    print("\n All Naver tests complete.")