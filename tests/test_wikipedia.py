"""
Tests for data_sources/wikipedia.py
Run from project root: PYTHONPATH=. python tests/test_wikipedia.py

No browser needed — plain REST API calls. Fast.
"""

from data_sources.wikipedia import (
    search_wikipedia,
    get_summary,
    get_sections,
    get_section_by_name,
    get_korean_title_info,
)


def test_search():
    print("\n=== Wikipedia Search ===")
    results = search_wikipedia("Parasite 2019 Korean film", limit=3)
    for r in results:
        print(f"  {r['title']} — {r['description']}")


def test_summary():
    print("\n=== Summary: Parasite ===")
    result = get_summary("Parasite (2019 film)")
    print(f"  Found: {result['found']}")
    print(f"  Title: {result['title']}")
    print(f"  Description: {result['description']}")
    print(f"  Summary: {result['summary'][:300]}...")
    print(f"  URL: {result['url']}")
    print(f"  Thumbnail: {result['thumbnail_url']}")


def test_sections():
    print("\n=== Sections: Squid Game ===")
    result = get_sections("Squid Game (TV series)")
    print(f"  Found: {result['found']}")
    print(f"  Available sections: {result['section_names']}")


def test_section_by_name():
    print("\n=== Plot Section: Parasite ===")
    result = get_section_by_name("Parasite (2019 film)", "Plot")
    print(f"  Found: {result['found']}")
    if result['found']:
        print(f"  Section: {result['section']}")
        print(f"  Content: {result['content'][:300]}...")

    print("\n=== Reception Section: Parasite ===")
    result = get_section_by_name("Parasite (2019 film)", "Reception")
    print(f"  Found: {result['found']}")
    if result['found']:
        print(f"  Content: {result['content'][:300]}...")


def test_smart_lookup_film():
    print("\n=== Smart Lookup: Parasite (film) ===")
    result = get_korean_title_info(
        "Parasite",
        year=2019,
        content_type="film",
        sections=["Plot", "Production", "Reception", "Accolades"]
    )
    print(f"  Found: {result['found']}")
    print(f"  Wikipedia title: {result.get('wikipedia_title')}")
    print(f"  Description: {result.get('description')}")
    print(f"  Summary: {str(result.get('summary', ''))[:200]}...")
    if result.get('sections'):
        for name, content in result['sections'].items():
            status = f"{len(content)} chars" if content else "not found"
            print(f"  Section '{name}': {status}")


def test_smart_lookup_drama():
    print("\n=== Smart Lookup: Squid Game (TV series) ===")
    result = get_korean_title_info(
        "Squid Game",
        year=2021,
        content_type="TV series",
        sections=["Plot", "Cast", "Production", "Reception"]
    )
    print(f"  Found: {result['found']}")
    print(f"  Wikipedia title: {result.get('wikipedia_title')}")
    print(f"  Description: {result.get('description')}")
    if result.get('sections'):
        for name, content in result['sections'].items():
            status = f"{len(content)} chars" if content else "not found"
            print(f"  Section '{name}': {status}")


def test_smart_lookup_drama_no_year():
    print("\n=== Smart Lookup: Crash Landing on You ===")
    result = get_korean_title_info(
        "Crash Landing on You",
        content_type="TV series",
        sections=["Plot", "Cast", "Ratings"]
    )
    print(f"  Found: {result['found']}")
    print(f"  Wikipedia title: {result.get('wikipedia_title')}")
    if result.get('sections'):
        for name, content in result['sections'].items():
            status = f"{len(content)} chars" if content else "not found"
            print(f"  Section '{name}': {status}")


if __name__ == "__main__":
    test_search()
    test_summary()
    test_sections()
    test_section_by_name()
    test_smart_lookup_film()
    test_smart_lookup_drama()
    test_smart_lookup_drama_no_year()
    print("\nAll Wikipedia tests complete.")

