"""
Tests for data_sources/naver.py
Run from project root: PYTHONPATH=. python tests/test_naver.py

Note: Each test opens a real browser — expect 10-15 seconds per test.
"""

from data_sources.naver import (
    search_movie,
    search_drama,
    get_movie_ratings,
)


def test_search_movie_korean():
    print("\n=== Movie Search: 살목지 (currently #1 at box office) ===")
    result = search_movie("살목지")
    if not result.get("found"):
        print("  ❌ Not found — Naver card not returned")
        return
    print(f"  Korean title: {result['korean_title']}")
    print(f"  English title: {result['english_title']}")
    print(f"  Year: {result['year']}")
    print(f"  Status: {result['status']}")
    print(f"  Genre: {result['genre']}")
    print(f"  Runtime: {result['runtime_minutes']} min")
    print(f"  Release date: {result['release_date']}")
    print(f"  Synopsis: {str(result['synopsis'])[:150]}...")
    print(f"  Box office rank: #{result['box_office_rank']}")
    print(f"  Cumulative audience: {result['cumulative_audience']}")
    print(f"  ⭐ Audience rating (실관람객): {result['audience_rating']}")
    print(f"  ⭐ Netizen rating (네티즌): {result['netizen_rating']}")
    print(f"  Cast:")
    for c in result["cast"][:5]:
        role_label = "감독" if c["is_director"] else c["role"]
        print(f"    {c['name']} — {role_label}")
    print(f"  Recommendations: {result['recommendations'][:5]}")


def test_search_movie_english():
    print("\n=== Movie Search: Parasite (English title) ===")
    result = search_movie("기생충")
    if not result.get("found"):
        print("  ❌ Not found")
        return
    print(f"  Korean title: {result['korean_title']}")
    print(f"  English title: {result['english_title']}")
    print(f"  Year: {result['year']}")
    print(f"  Genre: {result['genre']}")
    print(f"  ⭐ Audience rating: {result['audience_rating']}")
    print(f"  ⭐ Netizen rating: {result['netizen_rating']}")
    print(f"  Cast (top 3): {[c['name'] for c in result['cast'][:3]]}")


def test_search_drama():
    print("\n=== Drama Search: 완벽한 왕세자 (Perfect Crown) ===")
    result = search_drama("완벽한 왕세자")
    if not result.get("found"):
        print("  ❌ Not found")
        return
    print(f"  Korean title: {result['korean_title']}")
    print(f"  English title: {result['english_title']}")
    print(f"  Year: {result['year']}")
    print(f"  Status: {result['status']}")
    print(f"  ⭐ Audience rating: {result['audience_rating']}")
    print(f"  ⭐ Netizen rating: {result['netizen_rating']}")
    print(f"  Cast (top 3): {[c['name'] for c in result['cast'][:3]]}")


def test_get_ratings():
    print("\n=== Quick Rating Lookup: 살목지 ===")
    result = get_movie_ratings("살목지")
    print(f"  Title: {result['title']}")
    print(f"  Audience rating: {result['audience_rating']}")
    print(f"  Netizen rating: {result['netizen_rating']}")
    print(f"  Box office rank: #{result['box_office_rank']}")
    print(f"  Cumulative audience: {result['cumulative_audience']}")


if __name__ == "__main__":
    test_search_movie_korean()
    test_search_movie_english()
    test_search_drama()
    test_get_ratings()
    print("\nAll Naver tests complete.")