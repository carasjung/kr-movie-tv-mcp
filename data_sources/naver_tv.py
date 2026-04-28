"""
Naver TV scraper for Korean drama episode ratings and OST albums.
Uses Playwright — Naver is heavily JS-rendered.

Provides two unique data types unavailable elsewhere:
1. Episode-by-episode Nielsen Korea viewership ratings (시청률)
   - Source: Nielsen Korea via Naver
   - Covers up to last 30 episodes
2. OST album listings with Naver Vibe links
   - Album name, artist, release date, cover image

Search URL pattern:
    Ratings: search.naver.com/search.naver?where=nexearch&pkid=57&os={show_id}&query={title}+시청률
    Albums:  search.naver.com/search.naver?where=nexearch&pkid=57&os={show_id}&query={title}+관련앨범

The show_id (os parameter) is the Naver internal ID for the show.
It can be found in any Naver search result for the show.
"""

import re
import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

NAVER_SEARCH = "https://search.naver.com/search.naver"


# ── browser helper ────────────────────────────────────────────────────────────

def _get_html(url: str, wait_selector: str = "body", timeout: int = 15000) -> str:
    """Fetch a Naver page with Playwright and return rendered HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_selector(wait_selector, timeout=timeout)
            time.sleep(2)
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()
        finally:
            browser.close()
    return html


def _build_search_url(title: str, suffix: str) -> str:
    """Build a Naver search URL for a drama title with a suffix keyword."""
    query = f"{title} {suffix}"
    return f"{NAVER_SEARCH}?where=nexearch&sm=tab_etc&query={quote(query)}"


# ── episode ratings ───────────────────────────────────────────────────────────

def get_episode_ratings(title: str) -> dict:
    """
    Get Nielsen Korea episode viewership ratings for a Korean drama.
    Data is sourced from Nielsen Korea via Naver's broadcast info panel.
    Covers up to the last 30 episodes.

    Args:
        title: Korean drama title in Korean (e.g. "도깨비", "대군부인")
               Use the original Korean broadcast title, not English translation.

    Returns:
        Dict with channel, latest rating, highest rating, and per-episode data.
    """
    url = _build_search_url(title, "시청률")
    html = _get_html(url, wait_selector="div.cm_content_wrap, div.rating_wrap")
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "title": title,
        "found": False,
        "source": "Nielsen Korea via Naver",
    }

    # Check rating wrap exists
    rating_wrap = soup.select_one("div.rating_wrap")
    if not rating_wrap:
        return result

    result["found"] = True

    # Channel
    channel_tag = soup.select_one("span.channel")
    result["channel"] = channel_tag.get_text(strip=True) if channel_tag else None

    # Latest episode rating
    newest_box = soup.select_one("div.rating_bx.tag_newest")
    if newest_box:
        latest_pct = newest_box.select_one("span.percent_num")
        latest_ep = newest_box.select_one("span.rating_ep")
        result["latest_rating"] = float(latest_pct.get_text(strip=True)) if latest_pct else None
        result["latest_episode"] = _parse_episode_num(latest_ep.get_text(strip=True)) if latest_ep else None
    else:
        result["latest_rating"] = None
        result["latest_episode"] = None

    # Highest episode rating
    highest_box = soup.select_one("div.rating_bx.tag_highest")
    if highest_box:
        highest_pct = highest_box.select_one("span.percent_num")
        highest_ep = highest_box.select_one("span.rating_ep")
        result["highest_rating"] = float(highest_pct.get_text(strip=True)) if highest_pct else None
        result["highest_episode"] = _parse_episode_num(highest_ep.get_text(strip=True)) if highest_ep else None
    else:
        result["highest_rating"] = None
        result["highest_episode"] = None

    # Per-episode ratings from SVG chart text elements
    episodes = _parse_episode_chart(soup)
    result["episodes"] = episodes
    result["total_episodes_tracked"] = len(episodes)

    return result


def _parse_episode_num(text: str) -> int | None:
    """Parse episode number from '16회' → 16."""
    match = re.search(r"(\d+)회", text)
    return int(match.group(1)) if match else None


def _parse_episode_chart(soup: BeautifulSoup) -> list[dict]:
    """
    Extract per-episode ratings and air dates from the SVG chart.

    The SVG chart contains:
    - bb-text elements with rating values (e.g. "6.3", "7.9")
    - x-axis ticks with episode numbers (e.g. "1회") and dates (e.g. "04.10.")
    """
    episodes = []

    # Get rating values from bb-text elements
    # Filter out empty last element and negative placeholder
    rating_texts = soup.select("g.bb-texts-rank text.bb-text")
    ratings = []
    for t in rating_texts:
        val = t.get_text(strip=True)
        try:
            f = float(val)
            if f > 0:  # skip 0 placeholders
                ratings.append(f)
        except ValueError:
            pass

    # Get episode numbers and dates from x-axis ticks
    x_ticks = soup.select("g.bb-axis-x g.tick")
    ep_labels = []
    for tick in x_ticks:
        tspans = tick.select("tspan")
        if len(tspans) >= 2:
            ep_text = tspans[0].get_text(strip=True)
            date_text = tspans[1].get_text(strip=True)
            ep_num = _parse_episode_num(ep_text)
            if ep_num and date_text:
                ep_labels.append({
                    "episode": ep_num,
                    "date": date_text,
                })

    # Zip ratings with episode labels
    for i, label in enumerate(ep_labels):
        rating = ratings[i] if i < len(ratings) else None
        episodes.append({
            "episode": label["episode"],
            "air_date": label["date"],
            "rating": rating,
        })

    return episodes


# ── OST albums ────────────────────────────────────────────────────────────────

def get_ost_albums(title: str) -> dict:
    """
    Get OST album listings for a Korean drama from Naver.
    Returns all OST part albums with artist, release date, and Vibe links.

    Args:
        title: Korean drama title in Korean (e.g. "도깨비", "대군부인")

    Returns:
        Dict with list of OST albums.
    """
    url = _build_search_url(title, "관련앨범")
    html = _get_html(url, wait_selector="div.list_image_half, div.cm_tab_info_box")
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "title": title,
        "found": False,
        "albums": [],
    }

    album_list = soup.select_one("div.list_image_half")
    if not album_list:
        return result

    result["found"] = True

    for item in album_list.select("li"):
        link_tag = item.select_one("a.inner")
        if not link_tag:
            continue

        # Album name
        name_tag = item.select_one("strong.title span._text")
        album_name = name_tag.get_text(strip=True) if name_tag else None

        # Skip non-OST albums
        if album_name and "OST" not in album_name.upper():
            continue

        # Artist
        artist_tag = item.select_one("span.info_txt.line_1")
        artist = artist_tag.get_text(strip=True) if artist_tag else None

        # Release date
        date_tags = item.select("span.info_txt")
        release_date = None
        for tag in date_tags:
            if "line_1" not in tag.get("class", []):
                release_date = tag.get_text(strip=True)
                break

        # Cover image
        img_tag = item.select_one("div.thumb img")
        cover_url = img_tag.get("src") if img_tag else None

        # Naver Vibe URL
        vibe_url = link_tag.get("href", "")

        if album_name:
            result["albums"].append({
                "album_name": album_name,
                "artist": artist,
                "release_date": release_date,
                "cover_url": cover_url,
                "vibe_url": vibe_url,
            })

    result["total_albums"] = len(result["albums"])
    return result


# ── combined lookup ───────────────────────────────────────────────────────────

def get_drama_broadcast_info(title: str) -> dict:
    """
    Get both episode ratings and OST albums for a Korean drama in one call.
    Makes two separate Naver requests.

    Args:
        title: Korean drama title in Korean

    Returns:
        Dict with ratings and ost_albums combined.
    """
    ratings = get_episode_ratings(title)
    time.sleep(1)  # polite delay between requests
    ost = get_ost_albums(title)

    return {
        "title": title,
        "channel": ratings.get("channel"),
        "latest_rating": ratings.get("latest_rating"),
        "latest_episode": ratings.get("latest_episode"),
        "highest_rating": ratings.get("highest_rating"),
        "highest_episode": ratings.get("highest_episode"),
        "episodes": ratings.get("episodes", []),
        "total_episodes_tracked": ratings.get("total_episodes_tracked", 0),
        "ost_albums": ost.get("albums", []),
        "total_ost_albums": ost.get("total_albums", 0),
        "ratings_found": ratings.get("found", False),
        "ost_found": ost.get("found", False),
        "source": "Nielsen Korea via Naver",
    }