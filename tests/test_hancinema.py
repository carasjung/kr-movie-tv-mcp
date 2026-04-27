"""
Tests for data_sources/hancinema.py
Run from project root: PYTHONPATH=. python tests/test_hancinema.py

Note: Uses plain httpx — no browser needed, fast.
"""

from data_sources.hancinema import (
    get_korean_movies,
    get_korean_dramas,
    get_detail,
)


def test_korean_movies():
    print("\n=== Korean Movies (page 1) ===")
    results = get_korean_movies(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for m in results[:5]:
        print(f"  {m['title']} ({m['korean_title']}) — "
              f"{m['year']} | {m['genres']} | "
              f"Dir: {m['directors'][:1]}")


def test_korean_dramas():
    print("\n=== Korean Dramas (page 1) ===")
    results = get_korean_dramas(max_pages=1)
    print(f"Total scraped: {len(results)}")
    for d in results[:5]:
        print(f"  {d['title']} ({d['korean_title']}) — "
              f"{d['year']} | {d['genres']} | "
              f"Aired: {d['date']}")


def test_movie_detail():
    print("\n=== Movie Detail: Sweet Dream ===")
    result = get_detail("korean_movie_Sweet_Dream.php")
    print(f"  Title: {result['title']}")
    print(f"  Korean title: {result['korean_title']}")
    print(f"  Romanization: {result['romanization']}")
    print(f"  Year: {result['year']}")
    print(f"  Type: {result['content_type']}")
    print(f"  Genres: {result['genres']}")
    print(f"  Directors: {result['directors']}")
    print(f"  Writers: {result['writers']}")
    print(f"  Airing dates: {result['airing_dates']}")
    print(f"  Synopsis: {str(result['synopsis'])[:150]}...")
    print(f"  Cast (top 3):")
    for c in result["cast"][:3]:
        print(f"    {c['name']} ({c['korean_name']}) — {c['character']}")
    print(f"  Streaming: {result['streaming']}")


def test_drama_detail():
    print("\n=== Drama Detail: Phantom Lawyer ===")
    result = get_detail("korean_drama_Phantom_Lawyer.php")
    print(f"  Title: {result['title']}")
    print(f"  Korean title: {result['korean_title']}")
    print(f"  Romanization: {result['romanization']}")
    print(f"  Year: {result['year']}")
    print(f"  Network: {result['network']}")
    print(f"  Genres: {result['genres']}")
    print(f"  Directors: {result['directors']}")
    print(f"  Writers: {result['writers']}")
    print(f"  Airing dates: {result['airing_dates']}")
    print(f"  Episodes: {result['episode_count']}")
    print(f"  Synopsis: {str(result['synopsis'])[:150]}...")
    print(f"  Cast (top 3):")
    for c in result["cast"][:3]:
        print(f"    {c['name']} ({c['korean_name']}) — {c['character']}")
    print(f"  Streaming: {result['streaming']}")


if __name__ == "__main__":
    test_korean_movies()
    test_korean_dramas()
    test_movie_detail()
    test_drama_detail()
    print("\n All HanCinema tests complete.")