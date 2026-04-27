"""
JustWatch scraper for streaming availability data.
Provides where-to-watch info across Netflix, Apple TV, Viki, etc.
for Korean movies and TV shows internationally.

Uses Playwright — JustWatch is heavily JS-rendered.

URL patterns:
    Movies:   https://www.justwatch.com/{locale}/movie/{slug}
    TV shows: https://www.justwatch.com/{locale}/tv-show/{slug}

Slug is derived from the English title (e.g. "parasite", "squid-game").
"""

import re
import time
from urllib.parse import unquote, urlparse, parse_qs
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

BASE_URL = "https://www.justwatch.com"
DEFAULT_LOCALE = "us"  # change to "uk", "ca", "au" etc. for other regions

# Some regions use different locale codes or content type paths in their URLs
LOCALE_MAP = {
    "gb": "uk",   # UK uses /uk/ not /gb/
    "uk": "uk",
    "us": "us",
    "ca": "ca",
    "au": "au",
}

# Some regions use tv-series instead of tv-show in their URLs
TV_PATH_MAP = {
    "uk": "tv-series",
}


# ── browser helper ────────────────────────────────────────────────────────────

def _get_page_html(url: str, timeout: int = 20000) -> str:
    """Load a JustWatch page and return fully rendered HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            # Wait for the buybox (streaming offers) to render
            page.wait_for_selector("div.buybox-selector, div.buybox-container", timeout=timeout)
            time.sleep(2)  # let lazy content settle
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()
        finally:
            browser.close()
    return html


# ── slug helpers ──────────────────────────────────────────────────────────────

def title_to_slug(title: str, year: int = None) -> str:
    """
    Convert an English title to a JustWatch URL slug.
    e.g. "Squid Game" → "squid-game"
         "Parasite", year=2019 → "parasite-2019"
         "My Love from the Star" → "my-love-from-the-star"

    Tip: Pass year when a title has duplicates (e.g. remakes, same-name films).
    """
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if year:
        slug = f"{slug}-{year}"
    return slug


def _extract_redirect_url(href: str) -> str:
    """Extract the actual destination URL from JustWatch's redirect href."""
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        r = params.get("r", [None])[0]
        return unquote(r) if r else href
    except Exception:
        return href


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse_streaming_offers(soup: BeautifulSoup) -> list[dict]:
    """
    Parse all streaming offers from the buybox section.
    Returns list of providers with monetization type, price, quality, and URL.
    """
    offers = []
    seen = set()  # deduplicate by provider + type

    for offer_link in soup.select("div.buybox-selector a.offer"):
        provider_img = offer_link.select_one("img.provider-icon")
        if not provider_img:
            continue

        provider_name = provider_img.get("alt", "").strip()
        provider_logo = provider_img.get("src", "")
        if provider_logo.startswith("//"):
            provider_logo = "https:" + provider_logo

        # Monetization type: Subscription, Rent, Buy, Free
        label_tag = offer_link.select_one("p.offer__label__text")
        monetization = label_tag.get_text(strip=True) if label_tag else None

        # Price
        price_tag = offer_link.select_one("p.offer__label__price span")
        price = price_tag.get_text(strip=True) if price_tag else None

        # Quality: 4K, HD, SD
        quality_tag = offer_link.select_one("p.offer__presentation__icons__quality")
        quality = quality_tag.get_text(strip=True) if quality_tag else None

        # Direct URL (extract from JustWatch redirect)
        href = offer_link.get("href", "")
        watch_url = _extract_redirect_url(href)

        # Dedup key
        dedup_key = f"{provider_name}|{monetization}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        if provider_name:
            offers.append({
                "provider": provider_name,
                "provider_logo": provider_logo,
                "monetization_type": monetization,
                "price": price,
                "quality": quality,
                "watch_url": watch_url,
            })

    return offers


def _parse_sidebar_info(soup: BeautifulSoup) -> dict:
    """Parse the sidebar metadata: ratings, genres, runtime, age rating, country."""
    info = {}

    detail_sections = soup.select("div.poster-detail-infos")
    for section in detail_sections:
        heading = section.select_one("h3.poster-detail-infos__subheading")
        value_div = section.select_one("div.poster-detail-infos__value")
        if not heading or not value_div:
            continue

        key = heading.get_text(strip=True).lower()
        value_text = value_div.get_text(strip=True)

        if key == "director":
            info["director"] = value_text
        elif key == "genres":
            info["genres"] = [g.strip() for g in value_text.split(",")]
        elif key == "runtime":
            info["runtime"] = value_text
        elif key == "age rating":
            info["age_rating"] = value_text
        elif key == "production country":
            info["production_country"] = value_text
        elif key == "rating":
            # Parse multiple rating sources
            ratings = {}
            for rating_group in section.select("div.jw-scoring-listing__rating--group"):
                img = rating_group.select_one("img")
                source = img.get("alt", "").strip() if img else None
                score_div = rating_group.select_one("div")
                score = score_div.get_text(strip=True) if score_div else None
                if source and score:
                    ratings[source] = score
            info["ratings"] = ratings

    return info


def _parse_cast(soup: BeautifulSoup) -> list[dict]:
    """Parse cast members from the credits section."""
    cast = []
    for actor_div in soup.select("div.title-credits__actor"):
        name_tag = actor_div.select_one("span.title-credit-name")
        role_tag = actor_div.select_one("div.title-credits__actor--role--name strong")
        if name_tag:
            cast.append({
                "name": name_tag.get_text(strip=True),
                "character": role_tag.get_text(strip=True) if role_tag else None,
            })
    return cast[:15]


# ── public functions ──────────────────────────────────────────────────────────

def get_streaming_availability(
    title: str,
    content_type: str = "movie",
    locale: str = DEFAULT_LOCALE,
    slug: str = None,
) -> dict:
    """
    Get streaming availability and metadata for a Korean title on JustWatch.

    Args:
        title:        English title of the movie or TV show
        content_type: "movie" or "tv-show"
        locale:       Region code — "us", "gb", "ca", "au", "kr" etc.
                      Defaults to "us" for international availability
        slug:         Optional manual slug override if auto-generated one fails

    Returns:
        Dict with streaming offers, ratings, cast, and metadata.
    """
    url_slug = slug or title_to_slug(title)
    # Apply regional URL mappings
    url_locale = LOCALE_MAP.get(locale, locale)
    url_content_type = TV_PATH_MAP.get(url_locale, content_type) if content_type == "tv-show" else content_type
    url = f"{BASE_URL}/{url_locale}/{url_content_type}/{url_slug}"

    html = _get_page_html(url)
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "title": title,
        "slug": url_slug,
        "content_type": content_type,
        "locale": locale,
        "justwatch_url": url,
        "found": False,
    }

    # Check if page found a valid title
    page_title = soup.select_one("h1") or soup.select_one("title")
    if page_title and "not found" in page_title.get_text().lower():
        return result

    # Check for buybox or any offer — if present, page loaded correctly
    buybox = soup.select_one("div.buybox-container, div.buybox-selector, a.offer")
    if not buybox:
        return result

    result["found"] = True

    # Streaming summary text: "Currently you are able to watch X streaming on..."
    summary_tag = soup.select_one("section.spinning-texts p")
    result["streaming_summary"] = summary_tag.get_text(strip=True) if summary_tag else None

    # Parse streaming offers
    result["streaming_offers"] = _parse_streaming_offers(soup)

    # Convenience: list of just provider names by type
    def _mtype(o):
        return (o.get("monetization_type") or "").lower()

    result["streaming"] = [o["provider"] for o in result["streaming_offers"] if _mtype(o) == "subscription"]
    result["rent"] = [o["provider"] for o in result["streaming_offers"] if _mtype(o) == "rent"]
    result["buy"] = [o["provider"] for o in result["streaming_offers"] if _mtype(o) == "buy"]
    result["free"] = [o["provider"] for o in result["streaming_offers"] if "free" in _mtype(o)]

    # Sidebar metadata
    sidebar = _parse_sidebar_info(soup)
    result.update(sidebar)

    # Cast
    result["cast"] = _parse_cast(soup)

    # Synopsis
    synopsis_tag = soup.select_one("div#synopsis article div p")
    result["synopsis"] = synopsis_tag.get_text(strip=True) if synopsis_tag else None

    # Last updated timestamp
    timestamp_tag = soup.select_one("span.buybox-container__timestamp")
    result["last_updated"] = timestamp_tag.get_text(strip=True) if timestamp_tag else None

    return result


def get_streaming_for_multiple_regions(
    title: str,
    content_type: str = "movie",
    regions: list[str] = None,
) -> dict:
    """
    Get streaming availability for a title across multiple regions.
    Useful for showing where a Korean title is available internationally.

    Args:
        title:        English title
        content_type: "movie" or "tv-show"
        regions:      List of locale codes. Defaults to major English-speaking markets.

    Returns:
        Dict mapping region code to streaming offers.
    """
    if regions is None:
        regions = ["us", "gb", "ca", "au"]

    results = {}
    for region in regions:
        data = get_streaming_availability(title, content_type, locale=region)
        results[region] = {
            "streaming": data.get("streaming", []),
            "rent": data.get("rent", []),
            "buy": data.get("buy", []),
            "free": data.get("free", []),
            "found": data.get("found", False),
        }
        time.sleep(1)  # polite delay between regions

    return results