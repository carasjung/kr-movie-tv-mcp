"""
Korean entertainment awards scraper.

Covers:
1. AsianWiki (httpx + BeautifulSoup) — static HTML, fast:
   - KBS Drama Awards
   - MBC Drama Awards
   - SBS Drama Awards
   - Blue Dragon Film Awards

2. Baeksang Arts Awards official site (Playwright) — JS-rendered:
   - baeksangawards.co.kr/en/winners

All functions return structured winner + nominee data with show titles
linked back to AsianWiki slugs for cross-referencing.
"""

import re
import time
import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

ASIANWIKI_BASE = "https://asianwiki.com"
BAEKSANG_BASE = "https://www.baeksangawards.co.kr"

# Ceremony slug patterns on AsianWiki
CEREMONY_SLUGS = {
    "kbs_drama":     "KBS_Drama_Awards",
    "mbc_drama":     "MBC_Drama_Awards",
    "sbs_drama":     "SBS_Drama_Awards",
    "blue_dragon":   "Blue_Dragon_Film_Awards",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── AsianWiki helpers ─────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    """Fetch a static HTML page with httpx."""
    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def _get_ceremony_years(ceremony_key: str) -> list[dict]:
    """
    Get list of all available ceremony years and their URLs from AsianWiki index page.

    Args:
        ceremony_key: One of 'kbs_drama', 'mbc_drama', 'sbs_drama', 'blue_dragon'

    Returns:
        List of dicts with year and url.
    """
    slug = CEREMONY_SLUGS[ceremony_key]
    url = f"{ASIANWIKI_BASE}/{slug}"
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    years = []
    # Links follow pattern: /2025_SBS_Drama_Awards
    pattern = re.compile(r"/(\d{4})_" + slug.replace("_Awards", "") + r".*Awards?$", re.IGNORECASE)

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        match = pattern.match(href)
        if match:
            year = int(match.group(1))
            years.append({
                "year": year,
                "url": f"{ASIANWIKI_BASE}{href}",
                "title": a.get_text(strip=True),
            })

    # Deduplicate and sort descending
    seen = set()
    unique = []
    for y in years:
        if y["year"] not in seen:
            seen.add(y["year"])
            unique.append(y)

    return sorted(unique, key=lambda x: x["year"], reverse=True)


def _parse_ceremony_page(url: str, year: int, ceremony_name: str) -> dict:
    """
    Parse a single ceremony page from AsianWiki.
    Returns all categories with winners and nominees.
    """
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "ceremony": ceremony_name,
        "year": year,
        "url": url,
        "categories": [],
    }

    current_category = None

    # Walk through h3 headers (categories) and ul lists (winners/nominees)
    content = soup.select_one("div#mw-content-text, div.mw-parser-output")
    if not content:
        return result

    for element in content.children:
        if not hasattr(element, "name"):
            continue

        # Category header: h3 with span.mw-headline
        if element.name == "h3":
            headline = element.select_one("span.mw-headline")
            if headline:
                current_category = {
                    "category": headline.get_text(strip=True),
                    "winner": None,
                    "winner_show": None,
                    "nominees": [],
                }
                result["categories"].append(current_category)

        # Winner/nominees list
        elif element.name == "ul" and current_category is not None:
            items = element.select("> li")
            for item in items:
                text = item.get_text(strip=True)
                bold = item.select_one("b")

                if bold and "Award Winner" in bold.get_text():
                    # Parse winner
                    links = item.select("a")
                    if links:
                        current_category["winner"] = links[0].get_text(strip=True)
                        if len(links) > 1:
                            current_category["winner_show"] = links[1].get_text(strip=True)

                elif bold and "Nominees" in bold.get_text():
                    # Parse nominees from nested ul
                    nominee_list = item.select("ul li")
                    for nom in nominee_list:
                        nom_links = nom.select("a")
                        if nom_links:
                            nominee = {
                                "name": nom_links[0].get_text(strip=True),
                                "show": nom_links[1].get_text(strip=True) if len(nom_links) > 1 else None,
                            }
                            current_category["nominees"].append(nominee)

                elif not bold:
                    # Some ceremonies list without bold labels — treat as winner
                    links = item.select("a")
                    if links and not current_category["winner"]:
                        current_category["winner"] = links[0].get_text(strip=True)
                        if len(links) > 1:
                            current_category["winner_show"] = links[1].get_text(strip=True)

    # Filter out empty categories
    result["categories"] = [c for c in result["categories"] if c["winner"] or c["nominees"]]
    return result


# ── public AsianWiki functions ────────────────────────────────────────────────

def get_awards(ceremony_key: str, year: int) -> dict:
    """
    Get full awards data for a specific ceremony and year from AsianWiki.

    Args:
        ceremony_key: 'kbs_drama', 'mbc_drama', 'sbs_drama', or 'blue_dragon'
        year:         Award year (e.g. 2024, 2023)

    Returns:
        Dict with all categories, winners, and nominees.
    """
    slug = CEREMONY_SLUGS[ceremony_key]
    ceremony_name = slug.replace("_", " ")
    url = f"{ASIANWIKI_BASE}/{year}_{slug}"
    return _parse_ceremony_page(url, year, ceremony_name)


def get_recent_awards(ceremony_key: str, num_years: int = 3) -> list[dict]:
    """
    Get awards data for the most recent N years of a ceremony.

    Args:
        ceremony_key: 'kbs_drama', 'mbc_drama', 'sbs_drama', or 'blue_dragon'
        num_years:    Number of recent years to fetch (default 3)

    Returns:
        List of ceremony dicts, most recent first.
    """
    years = _get_ceremony_years(ceremony_key)[:num_years]
    results = []
    for year_info in years:
        data = _parse_ceremony_page(
            year_info["url"],
            year_info["year"],
            CEREMONY_SLUGS[ceremony_key].replace("_", " ")
        )
        results.append(data)
        time.sleep(0.5)
    return results


def search_awards_by_title(title: str, ceremony_key: str = None, years: int = 5) -> list[dict]:
    """
    Search for all awards won/nominated for a specific show title.

    Args:
        title:        Show or movie title to search for
        ceremony_key: Specific ceremony to search, or None for all
        years:        Number of recent years to search

    Returns:
        List of matching award entries with year, ceremony, category, win status.
    """
    ceremonies = [ceremony_key] if ceremony_key else list(CEREMONY_SLUGS.keys())
    matches = []
    title_lower = title.lower()

    for key in ceremonies:
        year_list = _get_ceremony_years(key)[:years]
        for year_info in year_list:
            data = _parse_ceremony_page(
                year_info["url"],
                year_info["year"],
                CEREMONY_SLUGS[key].replace("_", " ")
            )
            for cat in data["categories"]:
                # Check winner
                if cat["winner_show"] and title_lower in cat["winner_show"].lower():
                    matches.append({
                        "year": data["year"],
                        "ceremony": data["ceremony"],
                        "category": cat["category"],
                        "winner": cat["winner"],
                        "show": cat["winner_show"],
                        "won": True,
                    })
                # Check nominees
                for nom in cat["nominees"]:
                    if nom["show"] and title_lower in nom["show"].lower():
                        matches.append({
                            "year": data["year"],
                            "ceremony": data["ceremony"],
                            "category": cat["category"],
                            "winner": nom["name"],
                            "show": nom["show"],
                            "won": False,
                        })
            time.sleep(0.3)

    return matches


# ── Baeksang Awards ───────────────────────────────────────────────────────────

def get_baeksang_winners(year: int) -> dict:
    """
    Get Baeksang Arts Awards winners for a specific year from the official site.
    Uses Playwright — the site is React-rendered.

    Args:
        year: Award year (e.g. 2025, 2024)

    Returns:
        Dict with grand prizes and category winners.
    """
    url = f"{BAEKSANG_BASE}/en/winners#{year}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Wait for winner cards to render
            page.wait_for_selector("div.type-grand, div.type-main", timeout=15000)
            time.sleep(2)
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")

    result = {
        "ceremony": "Baeksang Arts Awards",
        "year": year,
        "url": url,
        "grand_prizes": [],
        "winners": [],
    }

    # Grand prizes: div.type-grand
    for grand in soup.select("div.type-grand"):
        category_tag = grand.select_one("p.grand-target span")
        winner_tag = grand.select_one("p.grand-prize")
        if category_tag and winner_tag:
            result["grand_prizes"].append({
                "category": category_tag.get_text(strip=True),
                "winner": winner_tag.get_text(strip=True),
            })

    # Regular winners: div.type-main
    for main in soup.select("div.type-main"):
        category_tag = main.select_one("p.prize")
        winner_tag = main.select_one("p.target")
        maker_tag = main.select_one("p.maker")
        if category_tag and winner_tag:
            result["winners"].append({
                "category": category_tag.get_text(strip=True),
                "winner": winner_tag.get_text(strip=True),
                "studio": maker_tag.get_text(strip=True) if maker_tag else None,
            })

    result["total_categories"] = len(result["grand_prizes"]) + len(result["winners"])
    return result


def get_recent_baeksang(num_years: int = 3) -> list[dict]:
    """
    Get Baeksang Arts Awards for the most recent N years.

    Args:
        num_years: Number of recent years to fetch

    Returns:
        List of ceremony dicts, most recent first.
    """
    from datetime import date
    current_year = date.today().year
    results = []
    for year in range(current_year, current_year - num_years, -1):
        data = get_baeksang_winners(year)
        if data["total_categories"] > 0:
            results.append(data)
        time.sleep(1)
    return results