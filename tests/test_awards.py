"""
Tests for data_sources/awards.py
Run from project root: PYTHONPATH=. python tests/test_awards.py

Note: AsianWiki tests use httpx (fast). Baeksang test uses Playwright (slower).
"""

from data_sources.awards import (
    get_ceremony_years,
    get_awards,
    get_recent_awards,
    search_awards_by_title,
    get_baeksang_winners,
)


def test_ceremony_years():
    print("\n=== SBS Drama Awards — Available Years ===")
    years = get_ceremony_years("sbs_drama")
    print(f"  Total years found: {len(years)}")
    for y in years[:5]:
        print(f"  {y['year']} — {y['url']}")


def test_sbs_drama_awards():
    print("\n=== SBS Drama Awards 2025 ===")
    result = get_awards("sbs_drama", 2025)
    print(f"  Ceremony: {result['ceremony']}")
    print(f"  Year: {result['year']}")
    print(f"  Categories: {len(result['categories'])}")
    for cat in result["categories"][:5]:
        print(f"  [{cat['category']}]")
        print(f"    Winner: {cat['winner']} — {cat['winner_show']}")
        if cat["nominees"]:
            print(f"    Nominees: {len(cat['nominees'])}")
            for nom in cat["nominees"][:2]:
                print(f"      {nom['name']} ({nom['show']})")


def test_kbs_drama_awards():
    print("\n=== KBS Drama Awards 2024 ===")
    result = get_awards("kbs_drama", 2024)
    print(f"  Categories: {len(result['categories'])}")
    for cat in result["categories"][:3]:
        print(f"  [{cat['category']}] {cat['winner']} — {cat['winner_show']}")


def test_blue_dragon():
    print("\n=== Blue Dragon Film Awards 2024 ===")
    result = get_awards("blue_dragon", 2024)
    print(f"  Categories: {len(result['categories'])}")
    for cat in result["categories"][:5]:
        print(f"  [{cat['category']}] {cat['winner']} — {cat['winner_show']}")


def test_search_by_title():
    print("\n=== Search Awards: Parasite ===")
    matches = search_awards_by_title("Parasite", ceremony_key="blue_dragon", years=5)
    print(f"  Total matches: {len(matches)}")
    for m in matches:
        status = "WON" if m["won"] else "nominated"
        print(f"  {m['year']} {m['ceremony']} — {m['category']}: "
              f"{m['winner']} [{status}]")


def test_baeksang_2025():
    print("\n=== Baeksang Arts Awards 2025 ===")
    result = get_baeksang_winners(2025)
    print(f"  Total categories: {result['total_categories']}")
    print(f"  Grand Prizes:")
    for gp in result["grand_prizes"]:
        print(f"    {gp['category']}: {gp['winner']}")
    print(f"  Category Winners (first 5):")
    for w in result["winners"][:5]:
        print(f"    [{w['category']}] {w['winner']} ({w.get('studio', '')})")


if __name__ == "__main__":
    test_ceremony_years()
    test_sbs_drama_awards()
    test_kbs_drama_awards()
    test_blue_dragon()
    test_search_by_title()
    test_baeksang_2025()
    print("\nAll awards tests complete.")