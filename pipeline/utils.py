"""
pipeline/utils.py — Shared helpers for all pipeline jobs.

Provides:
- Logging setup
- Rate limiting / polite delay
- Error handling wrappers
- Data transformation helpers (raw scraper output → DB schema)
"""

import time
import logging
from datetime import datetime, date
from typing import Any

# ── logging ───────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for a pipeline job."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ── rate limiting ─────────────────────────────────────────────────────────────

def polite_delay(seconds: float = 1.0):
    """Sleep between requests to avoid overwhelming sources."""
    time.sleep(seconds)


# ── data transformers ─────────────────────────────────────────────────────────

def parse_date(date_str: str | None) -> str | None:
    """
    Parse various date string formats into ISO format (YYYY-MM-DD).
    Handles MDL format (Dec 2, 2016), Naver format (2016.12.02), etc.
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",           # ISO: 2016-12-02
        "%b %d, %Y",          # MDL: Dec 2, 2016
        "%B %d, %Y",          # Full month: December 2, 2016
        "%Y.%m.%d.",          # Naver: 2016.12.02.
        "%Y.%m.%d",           # Naver: 2016.12.02
        "%d %b %Y",           # 02 Dec 2016
        "%Y/%m/%d",           # 2016/12/02
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try extracting just a year
    import re
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        return f"{year_match.group()}-01-01"

    return None


def parse_naver_air_date(episode_date: str, base_year: int = None) -> str | None:
    """
    Parse Naver episode air date format (e.g. '12.02.') into ISO date.
    Naver shows dates as MM.DD. without year.

    Args:
        episode_date: Date string like '12.02.' or '01.21.'
        base_year:    Year to use (defaults to current year)

    Returns:
        ISO date string e.g. '2016-12-02'
    """
    if not episode_date:
        return None

    import re
    match = re.match(r'(\d{2})\.(\d{2})\.?', episode_date.strip())
    if not match:
        return None

    month = int(match.group(1))
    day = int(match.group(2))
    year = base_year or datetime.now().year

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def clean_text(text: str | None) -> str | None:
    """Clean whitespace and encoding artifacts from text."""
    if not text:
        return None
    import re
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else None


def extract_year(text: str | None) -> int | None:
    """Extract a 4-digit year from a string."""
    if not text:
        return None
    import re
    match = re.search(r'\b(19|20)\d{2}\b', text)
    return int(match.group()) if match else None


def parse_runtime_minutes(text: str | None) -> int | None:
    """
    Parse runtime from various formats into total minutes.
    Handles: '2h 13min', '132 min', '1 hr. 15 min.', '132'
    """
    if not text:
        return None

    import re
    text = str(text).lower()

    # "2h 13min" or "2 hr 13 min"
    hm = re.search(r'(\d+)\s*h[rours.]*\s*(\d+)\s*m', text)
    if hm:
        return int(hm.group(1)) * 60 + int(hm.group(2))

    # "2h" only
    h_only = re.search(r'(\d+)\s*h[rours.]*', text)
    if h_only:
        return int(h_only.group(1)) * 60

    # "132 min" or just "132"
    m = re.search(r'(\d+)\s*m', text)
    if m:
        return int(m.group(1))

    # Plain number
    try:
        return int(text.strip())
    except ValueError:
        return None


def normalize_genres(genres: Any) -> list[str]:
    """Normalize genres from various formats to a clean list."""
    if not genres:
        return []
    if isinstance(genres, list):
        return [g.strip() for g in genres if g and g.strip()]
    if isinstance(genres, str):
        # Handle comma-separated string
        return [g.strip() for g in genres.split(',') if g.strip()]
    return []


def normalize_tags(tags: Any) -> list[str]:
    """Normalize MDL tags from various formats to a clean list."""
    if not tags:
        return []
    if isinstance(tags, list):
        # Strip voting suffix like "(Vote tags)"
        return [t.replace("(Vote tags)", "").strip() for t in tags if t.strip()]
    if isinstance(tags, str):
        import re
        tags = re.sub(r'\(Vote tags\)', '', tags)
        return [t.strip() for t in tags.split(',') if t.strip()]
    return []


def safe_float(value: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        return None


def extract_mdl_show_id(mdl_slug: str | None) -> str | None:
    """Extract the numeric MDL ID from a slug like '18452-goblin' → '18452'."""
    if not mdl_slug:
        return None
    import re
    match = re.match(r'^(\d+)', mdl_slug)
    return match.group(1) if match else None


def map_mdl_status(mdl_status: str | None) -> str | None:
    """Map MDL airing status to our DB status values."""
    if not mdl_status:
        return None
    status_map = {
        "currently airing": "Airing",
        "airing":           "Airing",
        "ongoing":          "Airing",
        "completed":        "Ended",
        "ended":            "Ended",
        "upcoming":         "Upcoming",
        "not yet aired":    "Upcoming",
        "announced":        "Upcoming",
        "on hiatus":        "Hiatus",
    }
    return status_map.get(mdl_status.lower().strip(), mdl_status)


def map_tmdb_status(tmdb_status: str | None) -> str | None:
    """Map TMDB status to our DB status values."""
    if not tmdb_status:
        return None
    status_map = {
        "returning series":  "Airing",
        "in production":     "Airing",
        "ended":             "Ended",
        "canceled":          "Ended",
        "planned":           "Upcoming",
    }
    return status_map.get(tmdb_status.lower().strip(), tmdb_status)


# ── batch helpers ─────────────────────────────────────────────────────────────

def batch(items: list, size: int = 50):
    """Split a list into chunks of a given size."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_with_retry(func, *args, retries: int = 3, delay: float = 5.0, **kwargs):
    """
    Run a function with automatic retry on failure.

    Args:
        func:    Function to call
        retries: Number of retry attempts
        delay:   Seconds to wait between retries

    Returns:
        Function result, or None if all retries fail.
    """
    logger = get_logger("retry")
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {retries} attempts failed for {func.__name__}: {e}")
                return None