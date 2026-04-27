"""
HanCinema scraper for Korean movies and dramas.
Uses httpx + BeautifulSoup (no Playwright needed — static HTML).

Install requirements:
    pip install httpx beautifulsoup4
"""

import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

BASE_URL = "https://www.hancinema.net"

LIST_URLS = {
    "movies":  f"{BASE_URL}/all_korean_movies.php",
    "dramas":  f"{BASE_URL}/all_korean_dramas.php",
}




# ── helpers ───────────────────────────────────────────────────────────────────

def _get_html(url: str) -> str:
    """Fetch a HanCinema page using Playwright and return rendered HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector("li", timeout=10000)
            time.sleep(1)
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()
        finally:
            browser.close()
    return html


def _get_paginated_html(base_url: str, max_pages: int = 1) -> list[str]:
    """
    Fetch multiple pages of a paginated HanCinema list.

    Args:
        base_url:  Base URL without ?p= parameter
        max_pages: Number of pages to fetch (each page = ~20 results)

    Returns:
        List of HTML strings, one per page.
    """
    pages = []
    for page_num in range(1, max_pages + 1):
        url = f"{base_url}?p={page_num}"
        pages.append(_get_html(url))
        if max_pages > 1:
            time.sleep(1)  # polite delay between pages
    return pages


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse_list_item(item, content_type: str) -> dict:
    """
    Parse a single <li> item from a HanCinema list page.

    Args:
        item:         BeautifulSoup <li> element
        content_type: "movie" or "drama"

    Returns:
        Dict with title, url, metadata.
    """
    result = {"content_type": content_type}

    info = item.select_one("div.work_info_short")
    if not info:
        return {}

    # Title link — first <a> in work_info_short
    title_link = info.select_one("a")
    if title_link:
        result["title"] = title_link.get_text(separator=" ").split("\n")[0].strip()
        # Korean title is in <span> inside the link
        korean_span = title_link.select_one("span")
        result["korean_title"] = korean_span.get_text(strip=True) if korean_span else None
        # Build full URL from relative href
        href = title_link.get("href", "")
        result["url"] = f"{BASE_URL}/{href}" if not href.startswith("http") else href
        result["slug"] = href.rstrip("/")
    else:
        result["title"] = None
        result["korean_title"] = None
        result["url"] = None
        result["slug"] = None

    # Poster image
    poster = item.select_one("div.work_info_short_poster img")
    if poster:
        src = poster.get("src", "")
        result["poster_url"] = f"https:{src}" if src.startswith("//") else src
    else:
        result["poster_url"] = None

    # Parse all <p> tags for metadata
    paragraphs = info.select("p")
    result["year"] = None
    result["genres"] = []
    result["directors"] = []
    result["writers"] = []
    result["date"] = None
    result["cast_preview"] = []

    for p in paragraphs:
        text = p.get_text(strip=True)

        # Type and year: "Movie, 1936" or "Drama, 1994"
        if re.search(r"\b(Movie|Drama)\b.*\b\d{4}\b", text):
            year_match = re.search(r"\b(\d{4})\b", text)
            result["year"] = int(year_match.group(1)) if year_match else None

        # Genres: links with itemprop="genre"
        elif p.select("a[itemprop='genre']"):
            result["genres"] = [a.get_text(strip=True) for a in p.select("a[itemprop='genre']")]

        # Directors
        elif "Directed by" in text:
            result["directors"] = [
                a.get_text(strip=True)
                for a in p.select("a[itemprop='director']")
            ]

        # Writers
        elif "Written by" in text:
            result["writers"] = [
                a.get_text(strip=True)
                for a in p.select("a[itemprop='author']")
            ]

        # Release/airing date
        elif p.select_one("span[itemprop='datePublished']"):
            result["date"] = p.select_one("span[itemprop='datePublished']").get_text(strip=True)

        # Cast preview: "With Actor1, Actor2,..."
        elif text.startswith("With "):
            cast_links = [
                a.get_text(strip=True)
                for a in p.select("a")
                if "cast" not in a.get("href", "")
            ]
            result["cast_preview"] = cast_links

    return result


def _parse_list_html(html: str, content_type: str) -> list[dict]:
    """Parse all list items from a HanCinema list page."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li")
    results = []
    for item in items:
        if item.select_one("div.work_info_short"):
            parsed = _parse_list_item(item, content_type)
            if parsed.get("title"):
                results.append(parsed)
    return results


# ── public list functions ─────────────────────────────────────────────────────

def get_korean_movies(max_pages: int = 1) -> list[dict]:
    """
    Scrape Korean movies from HanCinema.

    Args:
        max_pages: Number of pages to scrape (~20 results per page)

    Returns:
        List of movie dicts.
    """
    results = []
    pages = _get_paginated_html(LIST_URLS["movies"], max_pages)
    for html in pages:
        results.extend(_parse_list_html(html, "movie"))
    return results


def get_korean_dramas(max_pages: int = 1) -> list[dict]:
    """
    Scrape Korean dramas from HanCinema.

    Args:
        max_pages: Number of pages to scrape (~20 results per page)

    Returns:
        List of drama dicts.
    """
    results = []
    pages = _get_paginated_html(LIST_URLS["dramas"], max_pages)
    for html in pages:
        results.extend(_parse_list_html(html, "drama"))
    return results


# ── detail page ───────────────────────────────────────────────────────────────

def get_detail(slug: str) -> dict:
    """
    Scrape full details for a movie or drama from its HanCinema page.
    Slug is the relative URL from list results (e.g. 'korean_drama_Phantom_Lawyer.php').

    Args:
        slug: Relative URL slug from list results

    Returns:
        Dict with full metadata, cast, synopsis, and streaming links.
    """
    url = f"{BASE_URL}/{slug}" if not slug.startswith("http") else slug
    html = _get_html(url)
    soup = BeautifulSoup(html, "html.parser")

    result = {"slug": slug, "url": url}

    # Title
    title_tag = soup.select_one("div.work_info h1")
    result["title"] = title_tag.get_text(strip=True) if title_tag else None

    # Korean title and romanization: <h3>신이랑 법률사무소 | sin-i-rang...</h3>
    h3_tag = soup.select_one("div.work_info h3")
    if h3_tag:
        h3_text = h3_tag.get_text(strip=True)
        parts = [p.strip() for p in h3_text.split("|")]
        result["korean_title"] = parts[0] if parts else None
        result["romanization"] = parts[1] if len(parts) > 1 else None
    else:
        result["korean_title"] = None
        result["romanization"] = None

    # Type and year — find <p> containing a link to work_type filter
    type_year_p = None
    for p in soup.select("div.work_info p"):
        if p.select_one("a[href*='work_type']"):
            type_year_p = p
            break
    if type_year_p:
        links = type_year_p.select("a")
        result["content_type"] = links[0].get_text(strip=True) if links else None
        year_match = re.search(r"\b(\d{4})\b", type_year_p.get_text())
        result["year"] = int(year_match.group(1)) if year_match else None
    else:
        result["content_type"] = None
        result["year"] = None

    # Genres: <a itemprop="genre">
    result["genres"] = [
        a.get_text(strip=True)
        for a in soup.select("a[itemprop='genre']")
    ]

    # Synopsis box
    synopsis_div = soup.select_one("div.synopsis")
    if synopsis_div:
        # Director
        result["directors"] = [
            a.get_text(strip=True)
            for a in synopsis_div.select("a[itemprop='director']")
        ]
        # Writers
        result["writers"] = [
            a.get_text(strip=True)
            for a in synopsis_div.select("a[itemprop='author']")
        ]
        # Network/platform
        provider = synopsis_div.select_one("a[itemprop='provider']")
        result["network"] = provider.get_text(strip=True) if provider else None

        # Airing dates
        date_tag = synopsis_div.select_one("span[itemprop='datePublished']")
        result["airing_dates"] = date_tag.get_text(strip=True) if date_tag else None

        # Synopsis text — find the "Synopsis" label and grab following text
        synopsis_text = None
        full_text = synopsis_div.get_text(separator="\n")
        if "Synopsis" in full_text:
            synopsis_text = full_text.split("Synopsis")[-1].strip()
        result["synopsis"] = synopsis_text

        # Episodes, schedule, filming dates from free text
        p_texts = [p.get_text(strip=True) for p in synopsis_div.select("p")]
        for p_text in p_texts:
            ep_match = re.search(r"(\d+)\s+episodes?", p_text, re.IGNORECASE)
            if ep_match:
                result["episode_count"] = int(ep_match.group(1))
                break
        else:
            result["episode_count"] = None

    else:
        result["directors"] = []
        result["writers"] = []
        result["network"] = None
        result["airing_dates"] = None
        result["synopsis"] = None
        result["episode_count"] = None

    # Cast: <div class="cast_box"> → <li> items
    cast = []
    cast_items = soup.select("div.cast_box li")
    for item in cast_items:
        name_tag = item.select_one("div.work_info_short > a")
        korean_span = name_tag.select_one("span") if name_tag else None
        # Character is in the last <p> that isn't updates_emoji
        char_p = None
        for p in item.select("div.work_info_short p"):
            if "updates_emoji" not in p.get("class", []):
                char_p = p
        if name_tag:
            name = name_tag.get_text(strip=True)
            if korean_span:
                name = name.replace(korean_span.get_text(strip=True), "").strip()
            cast.append({
                "name": name,
                "korean_name": korean_span.get_text(strip=True).strip("()") if korean_span else None,
                "character": char_p.get_text(strip=True) if char_p else None,
                "profile_url": f"{BASE_URL}/{item.select_one('a').get('href', '')}" if item.select_one("a") else None,
            })
    result["cast"] = cast[:15]

    # Streaming/episodes
    streaming = []
    episode_items = soup.select("div.work_episodes li a[href]")
    seen_services = set()
    for ep in episode_items:
        text = ep.get_text(strip=True)
        service_match = re.search(r"Watch .+ on (.+)$", text)
        if service_match:
            service = service_match.group(1).strip()
            if service not in seen_services:
                seen_services.add(service)
                streaming.append({
                    "service": service,
                    "url": ep.get("href", ""),
                })
    result["streaming"] = streaming

    return result