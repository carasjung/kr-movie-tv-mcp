"""
Tests for data_sources/justwatch.py
Run from project root: PYTHONPATH=. python tests/test_justwatch.py

Note: Opens a real browser per test — expect 15-20 seconds per test.
"""

from data_sources.justwatch import (
    get_streaming_availability,
    get_streaming_for_multiple_regions,
    title_to_slug,
)


def test_slug_generation():
    print("\n=== Slug Generation ===")
    tests = [
        ("Parasite", None, "parasite"),
        ("Parasite", 2019, "parasite-2019"),
        ("Squid Game", None, "squid-game"),
        ("Crash Landing on You", None, "crash-landing-on-you"),
        ("My Love from the Star", None, "my-love-from-the-star"),
        ("Hellbound", None, "hellbound"),
    ]
    for title, year, expected in tests:
        slug = title_to_slug(title, year=year)
        status = "✓" if slug == expected else f"✗ (got {slug})"
        label = f"{title} ({year})" if year else title
        print(f"  {label} → {slug} {status}")


def test_movie_streaming():
    print("\n=== Movie: Parasite 2019 (US) ===")
    # Korean Parasite uses parasite-2019 slug to distinguish from 1982 US horror film
    result = get_streaming_availability("Parasite", content_type="movie", locale="us", slug="parasite-2019")
    print(f"  Found: {result['found']}")
    print(f"  URL: {result['justwatch_url']}")
    print(f"  Streaming: {result.get('streaming')}")
    print(f"  Rent: {result.get('rent')}")
    print(f"  Buy: {result.get('buy')}")
    print(f"  Free: {result.get('free')}")
    print(f"  Genres: {result.get('genres')}")
    print(f"  Runtime: {result.get('runtime')}")
    print(f"  Age rating: {result.get('age_rating')}")
    print(f"  Production country: {result.get('production_country')}")
    print(f"  Ratings: {result.get('ratings')}")
    print(f"  Director: {result.get('director')}")
    print(f"  Cast (top 3): {[c['name'] for c in result.get('cast', [])[:3]]}")
    print(f"  Last updated: {result.get('last_updated')}")
    print(f"\n  Full streaming offers:")
    for offer in result.get("streaming_offers", []):
        print(f"    {offer['provider']} — {offer['monetization_type']} "
              f"| {offer.get('quality')} | {offer.get('price')}")


def test_tv_show_streaming():
    print("\n=== TV Show: Squid Game (US) ===")
    result = get_streaming_availability("Squid Game", content_type="tv-show", locale="us")
    print(f"  Found: {result['found']}")
    print(f"  Streaming: {result.get('streaming')}")
    print(f"  Streaming summary: {result.get('streaming_summary')}")
    print(f"  Genres: {result.get('genres')}")
    print(f"  Age rating: {result.get('age_rating')}")
    print(f"  Ratings: {result.get('ratings')}")
    print(f"  Cast (top 3): {[c['name'] for c in result.get('cast', [])[:3]]}")


def test_multiple_regions():
    print("\n=== Multi-region: Crash Landing on You ===")
    results = get_streaming_for_multiple_regions(
        "Crash Landing on You",
        content_type="tv-show",
        regions=["us", "uk"]
    )
    for region, data in results.items():
        print(f"  {region.upper()}: streaming={data['streaming']} | "
              f"rent={data['rent']} | found={data['found']}")


if __name__ == "__main__":
    test_slug_generation()
    test_movie_streaming()
    test_tv_show_streaming()
    test_multiple_regions()
    print("\n All JustWatch tests complete.")