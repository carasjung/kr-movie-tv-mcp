"""
Naver Movies scraper for Korean movie and drama metadata.
Uses Playwright for JavaScript-rendered pages.

Naver Movies is Korea's dominant movie platform. Key unique data:
- 실관람객 평점 (verified ticket buyer rating)
- 네티즌 평점 (general netizen rating)
- Real-time box office rank + cumulative audience count

Search URL pattern:
    https://search.naver.com/search.naver?where=nexearch&query=영화+{title}
"""

import re
import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

NAVER_SEARCH_BASE = "https://search.naver.com/search.naver"


# ── browser helpers ───────────────────────────────────────────────────────────

def _get_page_html(url: str, wait_selector: str = "body", timeout: int = 15000) -> str:
    """Load a URL in headless Chromium and return rendered HTML."""
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
            time.sleep(1.5)
            html = page.content()
        except PlaywrightTimeout:
            html = page.content()
        finally:
            browser.close()
    return html


# ── search ────────────────────────────────────────────────────────────────────

def search_movie(title: str) -> dict:
    """
    Search Naver for a Korean movie or drama and return the top result.
    This uses Naver's integrated search which shows a rich movie card
    when the query matches a known title.

    Args:
        title: Movie or drama title in Korean or English

    Returns:
        Dict with full metadata from Naver's movie card, or empty dict if not found.
    """
    query = f"영화 {title}"
    url = f"{NAVER_SEARCH_BASE}?where=nexearch&sm=tab_etc&query={quote(query)}"
    html = _get_page_html(url, wait_selector="body")
    return _parse_movie_detail(html, title)


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse_movie_detail(html: str, search_title: str = "") -> dict:
    """
    Parse Naver's movie/drama detail card from a search results page.

    The card appears when Naver recognizes the query as a known title.
    Contains ratings, cast, synopsis, box office data.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {"search_title": search_title}

    # Find the main movie content wrapper
    wrap = soup.select_one("div._au_movie_content_wrap")
    if not wrap:
        result["found"] = False
        return result

    result["found"] = True

    # ── title ──────────────────────────────────────────────────────────────
    title_tag = wrap.select_one("h2.title strong._text")
    result["korean_title"] = title_tag.get_text(strip=True) if title_tag else None

    # Status: 상영중 (now showing), 개봉예정 (upcoming) etc.
    state_tag = wrap.select_one("h2.title span.state_end")
    result["status"] = state_tag.get_text(strip=True) if state_tag else None

    # Subtitle line: type (영화) | English title | year
    sub_txts = [s.get_text(strip=True) for s in wrap.select("div.sub_title span.txt")]
    result["content_type"] = sub_txts[0] if sub_txts else None
    result["english_title"] = sub_txts[1] if len(sub_txts) > 1 else None
    result["year"] = int(sub_txts[2]) if len(sub_txts) > 2 and sub_txts[2].isdigit() else None

    # ── metadata ───────────────────────────────────────────────────────────
    # Genre/country/runtime are in ONE dd tag separated by span.cm_bar_info
    # Structure: <dd>공포<span class="cm_bar_info"></span>대한민국<span>...</span>95분</dd>
    info_area = wrap.select_one("div.detail_info") or wrap.select_one("div.cm_info_box")
    if info_area:
        info_groups = info_area.select("div.info_group")
        if info_groups:
            # First group: replace bar spans with pipe separator then split
            first_dd = info_groups[0].select_one("dd")
            if first_dd:
                for span in first_dd.select("span"):
                    span.replace_with("|")
                segments = [s.strip() for s in first_dd.get_text().split("|") if s.strip()]
                result["genre"] = segments[0] if segments else None
                result["country"] = segments[1] if len(segments) > 1 else None
                runtime_match = None
                for seg in segments:
                    m = re.search(r"(\d+)분", seg)
                    if m:
                        runtime_match = m
                        break
                result["runtime_minutes"] = int(runtime_match.group(1)) if runtime_match else None
            else:
                result["genre"] = None
                result["country"] = None
                result["runtime_minutes"] = None

        # Release date: second info group
        if len(info_groups) > 1:
            date_dd = info_groups[1].select_one("dd")
            result["release_date"] = date_dd.get_text(strip=True) if date_dd else None
        else:
            result["release_date"] = None
    else:
        result["genre"] = None
        result["country"] = None
        result["runtime_minutes"] = None
        result["release_date"] = None

    # ── synopsis ───────────────────────────────────────────────────────────
    desc_tag = wrap.select_one("span.desc._text")
    result["synopsis"] = desc_tag.get_text(strip=True) if desc_tag else None

    # ── box office & audience ──────────────────────────────────────────────
    result["box_office_rank"] = None
    result["cumulative_audience"] = None

    item_boxes = wrap.select("div.item_box")
    for box in item_boxes:
        title_tag = box.select_one("strong.item_title")
        if not title_tag:
            continue
        title_text = title_tag.get_text(strip=True)

        if "순위" in title_text or "누적" in title_text:
            # "1위 / 198만명" — extract rank and audience
            info_span = box.select_one("span.normal_text")
            if info_span:
                ems = info_span.select("em")
                if len(ems) >= 1:
                    try:
                        result["box_office_rank"] = int(ems[0].get_text(strip=True))
                    except ValueError:
                        pass
                if len(ems) >= 2:
                    result["cumulative_audience"] = ems[1].get_text(strip=True) + "만명"

    # ── ratings ────────────────────────────────────────────────────────────
    # Naver has two distinct ratings — this is the key unique data
    result["audience_rating"] = None      # 실관람객 평점 (verified ticket buyers)
    result["netizen_rating"] = None       # 네티즌 평점 (general users)

    # Primary: item_area boxes (current films)
    rating_boxes = wrap.select("div.item_area")
    for box in rating_boxes:
        label = box.select_one("strong.item_title")
        score = box.select_one("span.this_text_bold")
        if label and score:
            label_text = label.get_text(strip=True)
            score_text = score.get_text(strip=True)
            try:
                score_val = float(score_text)
                if "실관람객" in label_text:
                    result["audience_rating"] = score_val
                elif "네티즌" in label_text:
                    result["netizen_rating"] = score_val
            except ValueError:
                pass

    # Fallback: lego_rating_box_see (older films use different layout)
    if result["audience_rating"] is None:
        rating_box = wrap.select_one("a.lego_rating_box_see")
        if rating_box:
            audience_score = rating_box.select_one("span.area_star_number")
            if audience_score:
                score_text = audience_score.get_text(strip=True).replace("10", "").strip()
                try:
                    result["audience_rating"] = float(score_text)
                except ValueError:
                    pass

    # ── cast ───────────────────────────────────────────────────────────────
    cast = []
    cast_area = wrap.select_one("div._cm_content_area_casting")
    if cast_area:
        for item in cast_area.select("li._item"):
            name_tag = item.select_one("strong.name a._text")
            role_tag = item.select_one("span.sub_text a._text")
            if name_tag:
                name = name_tag.get_text(strip=True)
                role = role_tag.get_text(strip=True) if role_tag else None
                # Distinguish director from actors
                is_director = role == "감독" if role else False
                cast.append({
                    "name": name,
                    "role": role,
                    "is_director": is_director,
                })
    result["cast"] = cast

    # ── recommendations ────────────────────────────────────────────────────
    recs = []
    rec_area = wrap.select_one("div._cm_content_area_recommend")
    if rec_area:
        for item in rec_area.select("li._item"):
            name_tag = item.select_one("strong.name a._text")
            if name_tag:
                recs.append(name_tag.get_text(strip=True))
    result["recommendations"] = recs

    return result


# ── convenience functions ─────────────────────────────────────────────────────

def get_movie_ratings(title: str) -> dict:
    """
    Get just the ratings for a movie — useful for quick rating lookups
    without fetching full detail.

    Args:
        title: Movie title in Korean

    Returns:
        Dict with audience_rating, netizen_rating, and box_office_rank.
    """
    data = search_movie(title)
    return {
        "title": data.get("korean_title") or title,
        "audience_rating": data.get("audience_rating"),
        "netizen_rating": data.get("netizen_rating"),
        "box_office_rank": data.get("box_office_rank"),
        "cumulative_audience": data.get("cumulative_audience"),
        "found": data.get("found", False),
    }