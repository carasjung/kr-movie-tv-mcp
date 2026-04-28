"""
Tests for data_sources/rottentomatoes.py
Run from project root: PYTHONPATH=. python tests/test_rottentomatoes.py
"""

from data_sources.rottentomatoes import get_rt_scores, get_rt_scores_batch


def test_korean_films():
    print("\n=== Korean Films ===")
    films = [
        ("Parasite", 2019),
        ("Train to Busan", 2016),
        ("The Wailing", 2016),
        ("Burning", 2018),
        ("Exhuma", 2024),
    ]
    for title, year in films:
        result = get_rt_scores(title, year=year)
        if result["found"]:
            print(f"  {result['title']} ({result.get('year', year)})")
            print(f"    Tomatometer (Western critics): {result['rt_tomatometer']}% [{result['rt_critics_rating']}]")
            print(f"    RT Audience (Western public):  {result['rt_audience_score']}%")
            print(f"    Weighted: {result['rt_weighted_score']}%")
        else:
            print(f"  {title} - Not found on RT")


def test_korean_dramas():
    print("\n=== Korean Dramas ===")
    dramas = [
        ("Squid Game", 2021),
        ("Hellbound", 2021),
        ("All of Us Are Dead", 2022),
    ]
    for title, year in dramas:
        result = get_rt_scores(title, year=year)
        if result["found"]:
            print(f"  {result['title']}")
            print(f"    Tomatometer: {result['rt_tomatometer']}%")
            print(f"    RT Audience: {result['rt_audience_score']}%")
        else:
            print(f"  {title} - Not found on RT")


def test_rating_differentiation():
    print("\n=== Rating Sources: Parasite ===")
    result = get_rt_scores("Parasite", year=2019)
    if result["found"]:
        print("  WESTERN (RT):")
        print(f"    Tomatometer (critics): {result['rt_tomatometer']}%")
        print(f"    Audience score:        {result['rt_audience_score']}%")
        print("  KOREAN (Naver):")
        print("    Verified audience:     9.08 / 10")
        print("  GLOBAL (TMDB):")
        print("    Community rating:      8.5 / 10")


def test_batch():
    print("\n=== Batch Lookup ===")
    titles = [
        {"title": "Parasite", "year": 2019},
        {"title": "Oldboy", "year": 2003},
        {"title": "The Handmaiden", "year": 2016},
    ]
    results = get_rt_scores_batch(titles)
    for r in results:
        if r["found"]:
            print(f"  {r['title']} - Tomatometer: {r['rt_tomatometer']}% / Audience: {r['rt_audience_score']}%")
        else:
            print(f"  {r.get('title')} - Not found")


if __name__ == "__main__":
    test_korean_films()
    test_korean_dramas()
    test_rating_differentiation()
    test_batch()
    print("\n All Rotten Tomatoes tests complete.")