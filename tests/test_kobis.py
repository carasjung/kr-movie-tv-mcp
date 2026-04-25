"""
Tests for data_sources/kobis.py
Run from project root: python -m tests.test_kobis
"""

from data_sources.kobis import (
    get_daily_boxoffice,
    get_weekly_boxoffice,
    get_all_films_boxoffice,
    get_movie_info,
    search_movies,
)


def test_daily_boxoffice():
    print("\n=== Daily Box Office (yesterday) ===")
    result = get_daily_boxoffice()
    print(f"Date: {result['date']}")
    print(f"Show range: {result['show_range']}")
    for entry in result["rankings"][:3]:
        rank_change = entry["rank_change"]
        status = "NEW" if entry["is_new_entry"] else f"change: {rank_change:+d}"
        print(f"  #{entry['rank']} {entry['title']} — "
              f"audience: {entry['audience_count']:,} | "
              f"cumulative: {entry['cumulative_audience']:,} | {status}")


def test_weekly_boxoffice():
    print("\n=== Weekly Box Office (last week) ===")
    result = get_weekly_boxoffice()
    print(f"Period: {result['period']}")
    print(f"Show range: {result['show_range']}")
    for entry in result["rankings"][:3]:
        print(f"  #{entry['rank']} {entry['title']} — "
              f"audience: {entry['audience_count']:,} | "
              f"screens: {entry['screen_count']}")


def test_weekend_boxoffice():
    print("\n=== Weekend Box Office (last weekend) ===")
    result = get_weekly_boxoffice(weekend_only=True)
    print(f"Period: {result['period']}")
    print(f"Show range: {result['show_range']}")
    for entry in result["rankings"][:3]:
        print(f"  #{entry['rank']} {entry['title']} — "
              f"sales: ₩{entry['sales_amount']:,} | "
              f"share: {entry['sales_share']}%")


def test_all_films_boxoffice():
    print("\n=== All Films (Korean + Foreign) Weekly ===")
    result = get_all_films_boxoffice()
    print(f"Show range: {result['show_range']}")
    for entry in result["rankings"][:5]:
        print(f"  #{entry['rank']} {entry['title']}")


def test_movie_info():
    print("\n=== Movie Info by Code ===")
    # First grab a code from the daily box office
    daily = get_daily_boxoffice()
    if daily["rankings"]:
        code = daily["rankings"][0]["movie_code"]
        title = daily["rankings"][0]["title"]
        print(f"Looking up: {title} ({code})")
        info = get_movie_info(code)
        print(f"  English title: {info.get('title_english')}")
        print(f"  Genres: {info.get('genres')}")
        print(f"  Runtime: {info.get('runtime_minutes')} min")
        print(f"  Directors: {[d['name'] for d in info.get('directors', [])]}")
        print(f"  Rating: {[a['rating'] for a in info.get('audits', [])]}")


def test_search_movies():
    print("\n=== Movie Search ===")
    # Test 1: search by English-friendly production year to confirm endpoint works
    result = search_movies(year="2024")
    print(f"Total 2024 Korean films: {result['total_count']}")
    for m in result["movies"][:3]:
        print(f"  {m['title']} ({m['title_english']}) — {m['production_year']} | {m['genres']}")

    # Test 2: search by Korean title
    result2 = search_movies(title="범죄도시")
    print(f"\nSearch '범죄도시' total results: {result2['total_count']}")
    for m in result2["movies"][:3]:
        print(f"  {m['title']} ({m['title_english']}) — {m['production_year']}")


if __name__ == "__main__":
    test_daily_boxoffice()
    test_weekly_boxoffice()
    test_weekend_boxoffice()
    test_all_films_boxoffice()
    test_movie_info()
    test_search_movies()
    print("\n All KOBIS tests complete.")