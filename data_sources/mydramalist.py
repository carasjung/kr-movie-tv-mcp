"""
MyDramaList (MDL) scraper for Korean drama discovery and metadata.
Uses Playwright for JavaScript-rendered pages.

Install requirements:
    pip install playwright httpx beautifulsoup4
    playwright install chromium
"""

import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

BASE_URL = "https://mydramalist.com"

# ── MDL search URLs ───────────────────────────────────────────────────────────
# ty=68 = Korean Drama only (removed variety/reality)
# co=3  = South Korea
SEARCH_URLS = {
    "upcoming":  f"{BASE_URL}/search?adv=titles&ty=68&co=3&st=2&so=popular",
    "popular":   f"{BASE_URL}/search?adv=titles&ty=68&co=3&so=popular",
    "airing":    f"{BASE_URL}/search?adv=titles&ty=68&co=3&st=1&so=relevance",
    "top":       f"{BASE_URL}/search?adv=titles&ty=68&co=3&st=3&so=top",
}


# ── browser helpers ───────────────────────────────────────────────────────────

def _get_page_html(url: str, wait_selector: str = ".box", timeout: int = 15000) -> str:
    """
    Load a URL in a headless Chromium browser and return the rendered HTML.

    Args:
        url:            URL to load
        wait_selector:  CSS selector to wait for before capturing HTML
        timeout:        Max milliseconds to wait for selector

    Returns:
        Full rendered HTML as a string.
    """
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
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_selector(wait_selector, timeout=timeout)
            # Small settle delay for lazy-loaded content
            time.sleep(1)
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()  # return whatever loaded
        finally:
            browser.close()

    return html


def _get_paginated_html(url: str, max_pages: int = 1) -> list[str]:
    """
    Load multiple pages of a paginated MDL search URL.

    Args:
        url:       Base search URL (without &page=N)
        max_pages: Number of pages to fetch (each page = 24 results)

    Returns:
        List of HTML strings, one per page.
    """
    pages = []
    for page_num in range(1, max_pages + 1):
        paginated_url = f"{url}&page={page_num}" if page_num > 1 else url
        html = _get_page_html(paginated_url)
        pages.append(html)
        if max_pages > 1:
            time.sleep(2)  # polite delay between pages
    return pages


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse_show_card(card) -> dict:
    """
    Parse a single MDL show card (div.box) into a clean dict.

    Args:
        card: BeautifulSoup element for the card

    Returns:
        Dict with show metadata.
    """
    result = {}

    # MDL ID from the div's id attribute (e.g. "mdl-18452" → 18452)
    raw_id = card.get("id", "")
    result["mdl_id"] = int(raw_id.replace("mdl-", "")) if raw_id.startswith("mdl-") else None

    # Title and slug
    title_tag = card.select_one("h6.text-primary.title a")
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)
        result["mdl_url"] = BASE_URL + title_tag.get("href", "")
        # slug is the href without leading slash
        result["slug"] = title_tag.get("href", "").lstrip("/")
    else:
        result["title"] = None
        result["mdl_url"] = None
        result["slug"] = None

    # Poster image
    img = card.select_one("img.cover")
    result["poster_url"] = img.get("src") if img else None

    # Ranking
    ranking_tag = card.select_one("div.ranking span")
    if ranking_tag:
        ranking_text = ranking_tag.get_text(strip=True).replace("#", "")
        result["mdl_ranking"] = int(ranking_text) if ranking_text.isdigit() else None
    else:
        result["mdl_ranking"] = None

    # Metadata line: "Korean Drama - 2026, 10 episodes"
    meta_tag = card.select_one("span.text-muted")
    if meta_tag:
        meta_text = meta_tag.get_text(strip=True)
        result["meta_raw"] = meta_text
        result["year"] = _extract_year(meta_text)
        result["episode_count"] = _extract_episodes(meta_text)
        result["content_type"] = _extract_type(meta_text)
    else:
        result["meta_raw"] = None
        result["year"] = None
        result["episode_count"] = None
        result["content_type"] = None

    # Rating (score out of 10)
    score_tag = card.select_one("span.p-l-xs.score")
    if score_tag:
        score_text = score_tag.get_text(strip=True)
        result["rating"] = float(score_text) if score_text else None
    else:
        result["rating"] = None

    # Description (second <p> in content div)
    content_div = card.select_one("div.col-xs-9.content")
    if content_div:
        paragraphs = content_div.find_all("p")
        # Find the paragraph with actual description text (not rating widget)
        desc_paragraphs = [
            p.get_text(strip=True)
            for p in paragraphs
            if p.get_text(strip=True) and not p.find("span", class_="rating")
        ]
        result["description"] = desc_paragraphs[0] if desc_paragraphs else None
    else:
        result["description"] = None

    # Watch online link (extract the actual destination URL from MDL redirect)
    watch_tag = card.select_one("a.btn-watch-online")
    if watch_tag:
        href = watch_tag.get("href", "")
        # MDL wraps links: /redirect?q=https%3A%2F%2F...
        match = re.search(r"[?&]q=([^&]+)", href)
        if match:
            from urllib.parse import unquote
            result["watch_url"] = unquote(match.group(1))
        else:
            result["watch_url"] = href
    else:
        result["watch_url"] = None

    return result


def _extract_year(meta: str) -> int | None:
    """Extract year from metadata string like 'Korean Drama - 2026, 10 episodes'."""
    match = re.search(r"\b(19|20)\d{2}\b", meta)
    return int(match.group()) if match else None


def _extract_episodes(meta: str) -> int | None:
    """Extract episode count from metadata string."""
    match = re.search(r"(\d+)\s+episode", meta, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_type(meta: str) -> str | None:
    """Extract content type from metadata string (e.g. 'Korean Drama')."""
    match = re.match(r"^([^-]+)", meta)
    return match.group(1).strip() if match else None


def _parse_cards_from_html(html: str) -> list[dict]:
    """Parse all show cards from a rendered HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.box[id^='mdl-']")
    return [_parse_show_card(card) for card in cards]


# ── public scraping functions ─────────────────────────────────────────────────

def get_upcoming_dramas(max_pages: int = 1) -> list[dict]:
    """
    Scrape upcoming Korean dramas sorted by popularity.

    Args:
        max_pages: Number of pages to scrape (24 results per page)

    Returns:
        List of show dicts.
    """
    results = []
    pages = _get_paginated_html(SEARCH_URLS["upcoming"], max_pages)
    for html in pages:
        results.extend(_parse_cards_from_html(html))
    return results


def get_popular_dramas(max_pages: int = 1) -> list[dict]:
    """
    Scrape most popular Korean dramas of all time.

    Args:
        max_pages: Number of pages to scrape (24 results per page)

    Returns:
        List of show dicts.
    """
    results = []
    pages = _get_paginated_html(SEARCH_URLS["popular"], max_pages)
    for html in pages:
        results.extend(_parse_cards_from_html(html))
    return results


def get_airing_dramas(max_pages: int = 1) -> list[dict]:
    """
    Scrape currently airing Korean dramas.

    Args:
        max_pages: Number of pages to scrape (24 results per page)

    Returns:
        List of show dicts.
    """
    results = []
    pages = _get_paginated_html(SEARCH_URLS["airing"], max_pages)
    for html in pages:
        results.extend(_parse_cards_from_html(html))
    return results


def get_top_dramas(max_pages: int = 1) -> list[dict]:
    """
    Scrape top-rated completed Korean dramas.

    Args:
        max_pages: Number of pages to scrape (24 results per page)

    Returns:
        List of show dicts.
    """
    results = []
    pages = _get_paginated_html(SEARCH_URLS["top"], max_pages)
    for html in pages:
        results.extend(_parse_cards_from_html(html))
    return results


def get_drama_details(slug: str) -> dict:
    """
    Scrape detailed info for a specific drama from its MDL page.
    Slug comes from the search results (e.g. '18452-goblin').

    Args:
        slug: MDL URL slug (e.g. '18452-goblin')

    Returns:
        Dict with full drama metadata from MDL detail page.
    """
    url = f"{BASE_URL}/{slug}"
    html = _get_page_html(url, wait_selector="h1.film-title")
    soup = BeautifulSoup(html, "html.parser")

    result = {"slug": slug, "mdl_url": url}

    # Title
    title_tag = soup.select_one("h1.film-title")
    result["title"] = title_tag.get_text(strip=True) if title_tag else None

    # Subtitle line: "쓸쓸하고 찬란하神 - 도깨비 ‧ Drama ‧ 2016 - 2017"
    subtitle_tag = soup.select_one("div.film-subtitle span")
    result["subtitle"] = subtitle_tag.get_text(strip=True) if subtitle_tag else None

    # Rating: <div class="col-film-rating"><div class="box deep-orange">8.8</div>
    rating_tag = soup.select_one("div.col-film-rating div.box")
    if rating_tag:
        rating_text = rating_tag.get_text(strip=True)
        try:
            result["rating"] = float(rating_text)
        except ValueError:
            result["rating"] = None
    else:
        result["rating"] = None

    # Votes: "Ratings: 8.8/10 from 165,176 users"
    votes_div = soup.select_one("div.hfs")
    if votes_div and "from" in votes_div.get_text():
        votes_text = votes_div.get_text(strip=True)
        votes_match = re.search(r"from ([\d,]+) users", votes_text)
        result["votes"] = votes_match.group(1).replace(",", "") if votes_match else None
    else:
        result["votes"] = None

    # Synopsis
    synopsis_tag = soup.select_one("div.show-synopsis")
    if synopsis_tag:
        # Remove "Edit Translation" link text
        for a in synopsis_tag.find_all("a"):
            a.decompose()
        result["synopsis"] = synopsis_tag.get_text(strip=True)
    else:
        result["synopsis"] = None

    # Details: from <ul class="list m-a-0 hidden-md-up"> with <b class="inline"> labels
    details = {}
    detail_list = soup.select("ul.list.m-a-0 li.list-item.p-a-0")
    for item in detail_list:
        label = item.select_one("b.inline")
        if label:
            key = label.get_text(strip=True).rstrip(":").lower().replace(" ", "_")
            # Get text after the label
            label.decompose()
            value = item.get_text(strip=True).lstrip(":").strip()
            if key and value:
                details[key] = value
    result["details"] = details

    # Native title: plain text after the "Native Title:" label
    native_li = soup.find("b", string=lambda t: t and "Native Title" in t)
    if native_li:
        native_parent = native_li.find_parent("li")
        if native_parent:
            # Remove the bold label text and get remaining text
            label = native_li.get_text(strip=True)
            full_text = native_parent.get_text(strip=True)
            native_text = full_text.replace(label, "").strip().lstrip(":").strip()
            result["native_title"] = native_text if native_text else None
        else:
            result["native_title"] = None
    else:
        result["native_title"] = None
    
    # Fallback: pull native_title from details dict if direct parse failed
    if not result.get("native_title") and result.get("details", {}).get("native_title"):
        result["native_title"] = result["details"]["native_title"]

    # Genres: <li class="list-item p-a-0 show-genres">
    genres_li = soup.select_one("li.show-genres")
    if genres_li:
        result["genres"] = [a.get_text(strip=True) for a in genres_li.select("a")]
    else:
        result["genres"] = []

    # Tags: <li class="list-item p-a-0 show-tags">
    tags_li = soup.select_one("li.show-tags")
    if tags_li:
        result["tags"] = [a.get_text(strip=True) for a in tags_li.select("span a")]
    else:
        result["tags"] = []

    # Cast: <li class="list-item col-sm-4"> with <b itempropx="name"> and <small class="text-muted">
    cast = []
    cast_items = soup.select("ul.credits li.list-item.col-sm-4")
    for item in cast_items:
        name_tag = item.select_one("b[itempropx='name']") or item.select_one("a.text-primary b")
        role_tag = item.select_one("small.text-muted")
        character_tag = item.select_one("small a")
        if name_tag:
            cast.append({
                "name": name_tag.get_text(strip=True),
                "character": character_tag.get_text(strip=True) if character_tag else None,
                "role_type": role_tag.get_text(strip=True) if role_tag else None,
            })
    result["cast"] = cast[:15]

    # Where to watch: <div class="box-body wts">
    watch_services = []
    wts_box = soup.select_one("div.wts")
    if wts_box:
        for col in wts_box.select("div.col-xs-12"):
            link_tag = col.select_one("a[href*='redirect']")
            if not link_tag:
                continue
            # Service name: text directly inside the <b> tag only
            service_b = col.select_one("b")
            service_name = service_b.get_text(strip=True) if service_b else link_tag.get_text(strip=True)
            # Type: look for span or small tag with subscription type
            # Type is plain text in the last div, after removing the service name
            all_text = col.get_text(strip=True)
            service_type = None
            for keyword in ["Subscription", "Free", "Rent", "Buy"]:
                if keyword.lower() in all_text.lower():
                    service_type = keyword
                    break
            
            # URL
            href = link_tag.get("href", "")
            match = re.search(r"[?&]q=([^&]+)", href)
            from urllib.parse import unquote
            watch_url = unquote(match.group(1)) if match else href
            watch_services.append({
                "service": service_name,
                "type": service_type,
                "url": watch_url,
            })
    result["where_to_watch"] = watch_services

    return result