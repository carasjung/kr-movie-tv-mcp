"""
Wikipedia API data source for Korean movies and dramas.
Uses the free Wikimedia REST API — no API key required.

Provides:
- Extended plot summaries (much longer than TMDB/HanCinema)
- Production background and development history
- Critical reception and cultural impact sections
- Infobox metadata (director, cast, distributor, budget, box office)
- Cultural context that AI agents can use for richer responses

API docs: https://en.wikipedia.org/api/rest_v1/
Rate limit: 200 requests/second — effectively unlimited for our use case.
"""

import re
import requests
from urllib.parse import quote

BASE_URL = "https://en.wikipedia.org/api/rest_v1"
ACTION_API = "https://en.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "KoreanEntertainmentMCP/1.0 (korean-entertainment-mcp; contact@example.com)",
    "Accept": "application/json",
}


# ── search ────────────────────────────────────────────────────────────────────

def search_wikipedia(query: str, limit: int = 5) -> list[dict]:
    """
    Search Wikipedia for pages matching a query.
    Useful for finding the correct article title before fetching full content.

    Args:
        query: Search term (e.g. "Parasite 2019 film", "Squid Game TV series")
        limit: Max number of results to return

    Returns:
        List of dicts with title, description, and url.
    """
    response = requests.get(
        "https://en.wikipedia.org/w/rest.php/v1/search/page",
        headers=HEADERS,
        params={"q": query, "limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    return [
        {
            "title": p.get("title"),
            "description": p.get("description"),
            "url": f"https://en.wikipedia.org/wiki/{quote(p.get('title', '').replace(' ', '_'))}",
        }
        for p in data.get("pages", [])
    ]


# ── summary ───────────────────────────────────────────────────────────────────

def get_summary(title: str) -> dict:
    """
    Get a concise summary for a Wikipedia article.
    Returns the introductory paragraph + key metadata.

    Args:
        title: Exact Wikipedia article title (e.g. "Parasite (2019 film)")

    Returns:
        Dict with summary, description, thumbnail, and page metadata.
    """
    encoded = quote(title.replace(" ", "_"))
    response = requests.get(
        f"{BASE_URL}/page/summary/{encoded}",
        headers=HEADERS,
        timeout=10,
    )

    if response.status_code == 404:
        return {"found": False, "title": title}

    response.raise_for_status()
    data = response.json()

    thumbnail = data.get("thumbnail", {})
    return {
        "found": True,
        "title": data.get("title"),
        "display_title": data.get("displaytitle"),
        "description": data.get("description"),
        "summary": data.get("extract"),       # introductory paragraph(s)
        "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
        "thumbnail_url": thumbnail.get("source") if thumbnail else None,
        "last_edited": data.get("timestamp"),
        "page_id": data.get("pageid"),
    }


# ── full sections ─────────────────────────────────────────────────────────────

def get_sections(title: str) -> dict:
    """
    Get the full article broken into named sections.
    Useful for extracting Plot, Production, Reception, Cultural impact etc.
    Uses the Action API extracts endpoint for reliability.

    Args:
        title: Exact Wikipedia article title

    Returns:
        Dict with article title and list of sections (name + content).
    """
    # Step 1: get section list via Action API parse
    sections_resp = requests.get(
        ACTION_API,
        headers=HEADERS,
        params={
            "action": "parse",
            "page": title,
            "prop": "sections",
            "format": "json",
        },
        timeout=10,
    )

    if sections_resp.status_code != 200:
        return {"found": False, "title": title, "sections": [], "section_names": []}

    sections_data = sections_resp.json()
    if "error" in sections_data:
        return {"found": False, "title": title, "sections": [], "section_names": []}

    raw_sections = sections_data.get("parse", {}).get("sections", [])
    if not raw_sections:
        return {"found": False, "title": title, "sections": [], "section_names": []}

    # Step 2: fetch full article text and split by sections
    text_resp = requests.get(
        ACTION_API,
        headers=HEADERS,
        params={
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "explaintext": True,
            "exsectionformat": "wiki",
            "format": "json",
        },
        timeout=15,
    )

    full_text = ""
    if text_resp.ok:
        pages = text_resp.json().get("query", {}).get("pages", {})
        for page_data in pages.values():
            full_text = page_data.get("extract", "")
            break

    # Step 3: build sections list from the section metadata
    sections = []

    # Add introduction (text before first section header)
    if full_text:
        first_section_marker = None
        for s in raw_sections:
            if s.get("line"):
                first_section_marker = f"== {s['line']} =="
                break
        if first_section_marker and first_section_marker in full_text:
            intro = full_text.split(first_section_marker)[0].strip()
        else:
            intro = full_text[:2000]  # fallback: first 2000 chars
        if intro:
            sections.append({
                "name": "Introduction",
                "level": 1,
                "content": intro,
            })

    # Add named sections by splitting on == headers ==
    for i, section_meta in enumerate(raw_sections):
        section_name = section_meta.get("line", "")
        level = int(section_meta.get("level", 2))
        if not section_name or not full_text:
            sections.append({
                "name": section_name,
                "level": level,
                "content": "",
            })
            continue

        # Find this section's content in the full text
        header = f"{'=' * level} {section_name} {'=' * level}"
        if header in full_text:
            after_header = full_text.split(header, 1)[1]
            # Content ends at the next same-or-higher level header
            next_header_pattern = r"\n={1," + str(level) + r"}[^=]"
            import re as _re
            match = _re.search(next_header_pattern, after_header)
            content = after_header[:match.start()].strip() if match else after_header.strip()
        else:
            content = ""

        sections.append({
            "name": section_name,
            "level": level,
            "content": content,
        })

    return {
        "found": True,
        "title": title,
        "sections": sections,
        "section_names": [s["name"] for s in sections],
    }


def get_section_by_name(title: str, section_name: str) -> dict:
    """
    Get a specific section from a Wikipedia article by name.
    Common section names for Korean films/dramas:
        "Plot", "Cast", "Production", "Reception", "Accolades",
        "Soundtrack", "Cultural impact", "Ratings"

    Args:
        title:        Wikipedia article title
        section_name: Section name to retrieve (case-insensitive partial match)

    Returns:
        Dict with section name and content, or not_found if missing.
    """
    article = get_sections(title)
    if not article.get("found"):
        return {"found": False, "title": title, "section": section_name}

    section_name_lower = section_name.lower()
    for section in article["sections"]:
        if section_name_lower in section["name"].lower():
            return {
                "found": True,
                "title": title,
                "section": section["name"],
                "content": section["content"],
            }

    return {
        "found": False,
        "title": title,
        "section": section_name,
        "available_sections": article["section_names"],
    }


# ── smart lookup ──────────────────────────────────────────────────────────────

def get_korean_title_info(
    title: str,
    year: int = None,
    content_type: str = "film",
    sections: list[str] = None,
) -> dict:
    """
    Smart lookup for a Korean movie or drama on Wikipedia.
    Handles disambiguation automatically by trying common title patterns.

    Args:
        title:        English title (e.g. "Parasite", "Squid Game")
        year:         Release year for disambiguation (e.g. 2019)
        content_type: "film", "TV series", or "drama" — used in disambiguation
        sections:     List of section names to fetch (e.g. ["Plot", "Reception"])
                      If None, returns summary only.

    Returns:
        Dict with summary and requested sections.
    """
    # Build candidate article titles to try in order
    candidates = []
    if year and content_type:
        candidates.append(f"{title} ({year} {content_type})")
        candidates.append(f"{title} ({year} South Korean {content_type})")
    if content_type:
        candidates.append(f"{title} ({content_type})")
        candidates.append(f"{title} (South Korean {content_type})")
    candidates.append(title)

    # Try each candidate until one is found
    summary = None
    for candidate in candidates:
        summary = get_summary(candidate)
        if summary.get("found"):
            break

    # If still not found try search
    if not summary or not summary.get("found"):
        search_results = search_wikipedia(f"{title} Korean {content_type}")
        if search_results:
            summary = get_summary(search_results[0]["title"])

    if not summary or not summary.get("found"):
        return {"found": False, "title": title}

    result = {
        "found": True,
        "wikipedia_title": summary["title"],
        "description": summary["description"],
        "summary": summary["summary"],
        "url": summary["url"],
        "thumbnail_url": summary["thumbnail_url"],
        "last_edited": summary["last_edited"],
    }

    # Fetch specific sections if requested
    # Wikipedia section names aren't standardized — try aliases for common sections
    SECTION_ALIASES = {
        "Plot": ["Plot", "Synopsis", "Story", "Series overview", "Premise", "Episodes"],
        "Cast": ["Cast", "Cast and characters", "Characters", "Main cast"],
        "Production": ["Production", "Development", "Filming", "Background"],
        "Reception": ["Reception", "Critical response", "Critical reception", "Response"],
        "Accolades": ["Accolades", "Awards", "Awards and nominations"],
        "Ratings": ["Ratings", "Viewership ratings", "Television ratings", "Audience", "Viewership"],
        "Soundtrack": ["Soundtrack", "Music", "OST", "Original soundtrack"],
        "Cultural impact": ["Cultural impact", "Cultural significance", "Impact", "Legacy"],
    }

    if sections:
        result["sections"] = {}
        for section_name in sections:
            # Try the requested name first, then aliases
            aliases = SECTION_ALIASES.get(section_name, [section_name])
            found_content = None
            for alias in aliases:
                section_data = get_section_by_name(summary["title"], alias)
                if section_data.get("found"):
                    found_content = section_data["content"]
                    break
            result["sections"][section_name] = found_content

    return result


# ── helpers ───────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags and clean up Wikipedia article text."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove reference markers like [1], [2]
    text = re.sub(r"\[\d+\]", "", text)
    # Remove edit section markers
    text = re.sub(r"\[edit\]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text