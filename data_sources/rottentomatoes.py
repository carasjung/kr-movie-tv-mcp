"""
Rotten Tomatoes data source for Western critic and audience scores.
Uses the rottentomatoes-python package which scrapes RT directly.

Install: pip install rottentomatoes-python

Provides clearly labeled Western ratings to differentiate from Korean ratings:
    rt_tomatometer    = % of Western professional critics (positive reviews)
    rt_audience_score = % of Western RT users (positive ratings)
    rt_critics_rating = Certified Fresh / Fresh / Rotten

vs Korean ratings from other sources:
    naver_audience_rating = Korean verified ticket buyers (0-10)
    naver_netizen_rating  = Korean general public (0-10)
    mdl_rating            = International K-drama fan score (0-10)
    tmdb_rating           = Global community score (0-10)
"""

import rottentomatoes as rt


def get_rt_scores(title: str, year: int = None) -> dict:
    """
    Get Rotten Tomatoes scores for a Korean movie or TV show.

    Args:
        title: English title (required)
        year:  Release year for disambiguation (recommended)

    Returns:
        Dict with clearly labeled RT scores or found=False if unavailable.
    """
    try:
        movie = rt.Movie(title)
        tomatometer = movie.tomatometer
        audience = movie.audience_score
        return {
            "found": True,
            "source": "Rotten Tomatoes",
            "title": title,
            "year": movie.year_released if hasattr(movie, 'year_released') else year,
            "rt_tomatometer": tomatometer,
            "rt_audience_score": audience,
            "rt_critics_rating": _critics_rating(tomatometer),
            "rt_weighted_score": movie.weighted_score,
            "rt_url": movie.url if hasattr(movie, 'url') else None,
            "genres": movie.genres if hasattr(movie, 'genres') else [],
            "rating": movie.rating if hasattr(movie, 'rating') else None,
            "duration": movie.duration if hasattr(movie, 'duration') else None,
        }
    except LookupError:
        return {"found": False, "title": title, "source": "Rotten Tomatoes"}
    except Exception as e:
        return {"found": False, "title": title, "source": "Rotten Tomatoes", "error": str(e)}


def _critics_rating(tomatometer: int | None) -> str | None:
    if tomatometer is None:
        return None
    return "Fresh" if tomatometer >= 60 else "Rotten"


def get_rt_scores_batch(titles: list[dict]) -> list[dict]:
    """
    Get RT scores for multiple titles.

    Args:
        titles: List of dicts e.g. [{"title": "Parasite", "year": 2019}, ...]

    Returns:
        List of RT score dicts in same order as input.
    """
    import time
    results = []
    for item in titles:
        result = get_rt_scores(item["title"], item.get("year"))
        results.append(result)
        time.sleep(0.5)
    return results