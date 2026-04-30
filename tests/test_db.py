"""
tests/test_db.py — Verify Supabase connection and basic upsert/read operations.
Run from project root: PYTHONPATH=. python tests/test_db.py

This test inserts real rows, reads them back, and cleans up after itself.
It does NOT test every function — just enough to confirm the DB layer works.
"""

from db.queries import (
    upsert_movie,
    get_movie_by_tmdb_id,
    upsert_show,
    get_show_by_tmdb_id,
    upsert_person,
    upsert_movie_cast,
    get_movie_cast,
    upsert_episodes_bulk,
    get_episodes,
    upsert_streaming_bulk,
    get_streaming_for_movie,
    upsert_boxoffice,
    get_weekly_boxoffice,
    upsert_award,
    get_awards_for_movie,
    _supabase,
)


# ── test data ─────────────────────────────────────────────────────────────────

TEST_MOVIE = {
    "tmdb_id": "test_496243",
    "title_english": "Parasite (TEST)",
    "title_korean": "기생충",
    "release_year": 2019,
    "genres": ["Thriller", "Drama", "Comedy"],
    "tmdb_rating": 8.5,
    "naver_audience_rating": 9.08,
    "rt_tomatometer": 99,
    "rt_audience_score": 90,
    "rt_critics_rating": "Certified Fresh",
    "country": "South Korea",
    "runtime_minutes": 132,
}

TEST_SHOW = {
    "tmdb_id": "test_94796",
    "title_english": "Crash Landing on You (TEST)",
    "title_korean": "사랑의 불시착",
    "year": 2019,
    "status": "Ended",
    "total_episodes": 16,
    "network": "tvN",
    "mdl_rating": 8.9,
    "naver_highest_rating": 21.7,
    "genres": ["Romance", "Drama"],
}

TEST_PERSON = {
    "tmdb_person_id": "test_21684",
    "name_english": "Song Kang-ho (TEST)",
    "name_korean": "송강호",
    "known_for_department": "Acting",
}


# ── tests ─────────────────────────────────────────────────────────────────────

def test_movie_upsert_and_read():
    print("\n=== Movie: upsert + read ===")
    row = upsert_movie(TEST_MOVIE)
    print(f"  Upserted: {row.get('title_english')} (id: {row.get('id')[:8]}...)")

    fetched = get_movie_by_tmdb_id("test_496243")
    assert fetched["title_korean"] == "기생충", "Korean title mismatch"
    assert fetched["tmdb_rating"] == 8.5, "TMDB rating mismatch"
    assert fetched["rt_tomatometer"] == 99, "RT tomatometer mismatch"
    print(f"  Read back: {fetched['title_english']}")
    print(f"  TMDB rating: {fetched['tmdb_rating']}")
    print(f"  Naver audience: {fetched['naver_audience_rating']}")
    print(f"  RT tomatometer: {fetched['rt_tomatometer']}%")
    print("  Movie test passed")
    return fetched["id"]


def test_show_upsert_and_read():
    print("\n=== Show: upsert + read ===")
    row = upsert_show(TEST_SHOW)
    print(f"  Upserted: {row.get('title_english')} (id: {row.get('id')[:8]}...)")

    fetched = get_show_by_tmdb_id("test_94796")
    assert fetched["mdl_rating"] == 8.9, "MDL rating mismatch"
    assert fetched["naver_highest_rating"] == 21.7, "Naver rating mismatch"
    print(f"  MDL rating: {fetched['mdl_rating']}")
    print(f"  Naver highest: {fetched['naver_highest_rating']}%")
    print("  Show test passed")
    return fetched["id"]


def test_cast(movie_id: str):
    print("\n=== Cast: upsert + read ===")
    person = upsert_person(TEST_PERSON)
    person_id = person["id"]
    print(f"  Person upserted: {person['name_english']}")

    upsert_movie_cast(movie_id, person_id, {
        "character_name": "Ki-taek",
        "role_type": "Lead",
        "cast_order": 1,
    })

    cast = get_movie_cast(movie_id)
    assert len(cast) > 0, "No cast rows returned"
    print(f"  Cast rows: {len(cast)}")
    print(f"  First cast: {cast[0]['people']['name_english']} as {cast[0]['character_name']}")
    print("  Cast test passed")
    return person_id


def test_episodes(show_id: str):
    print("\n=== Episodes: bulk upsert + read ===")
    episodes = [
        {"episode_number": 1, "air_date": "2019-12-14", "nielsen_rating": 6.6, "channel": "tvN"},
        {"episode_number": 2, "air_date": "2019-12-15", "nielsen_rating": 7.1, "channel": "tvN"},
        {"episode_number": 16, "air_date": "2020-02-16", "nielsen_rating": 21.7, "channel": "tvN"},
    ]
    upsert_episodes_bulk(show_id, episodes)
    rows = get_episodes(show_id)
    assert len(rows) == 3, f"Expected 3 episodes, got {len(rows)}"
    print(f"  Episodes stored: {len(rows)}")
    print(f"  Peak rating: {max(r['nielsen_rating'] for r in rows)}%")
    print("  Episodes test passed")


def test_streaming(movie_id: str):
    print("\n=== Streaming: bulk upsert + read ===")
    offers = [
        {
            "movie_id": movie_id,
            "show_id": None,
            "region": "us",
            "provider": "Kanopy",
            "monetization_type": "Free",
            "quality": "HD",
        },
        {
            "movie_id": movie_id,
            "show_id": None,
            "region": "us",
            "provider": "Amazon Video",
            "monetization_type": "Rent",
            "quality": "4K",
            "price": "$3.99",
        },
    ]
    upsert_streaming_bulk(offers)
    rows = get_streaming_for_movie(movie_id, region="us")
    assert len(rows) >= 2, f"Expected 2 streaming rows, got {len(rows)}"
    print(f"  Streaming options: {len(rows)}")
    for r in rows:
        print(f"    {r['provider']} — {r['monetization_type']} ({r['region'].upper()})")
    print("  Streaming test passed")


def test_boxoffice(movie_id: str):
    print("\n=== Box office: upsert + read ===")
    upsert_boxoffice({
        "kobis_movie_code": "TEST20190001",
        "movie_id": movie_id,
        "week_start": "2019-06-03",
        "period_type": "weekly",
        "rank": 1,
        "audience_count": 1200000,
        "sales_amount": 10800000000,
        "sales_share": 68.5,
        "screen_count": 2006,
    })
    rows = get_weekly_boxoffice(week_start="2019-06-03")
    assert len(rows) > 0, "No box office rows returned"
    print(f"  Box office rows: {len(rows)}")
    print(f"  #1: {rows[0].get('movies', {}).get('title_english')} — "
          f"{rows[0]['audience_count']:,} admissions")
    print("  Box office test passed")


def test_awards(movie_id: str):
    print("\n=== Awards: upsert + read ===")
    award = upsert_award({
        "ceremony": "Blue Dragon Film Awards",
        "year": 2019,
        "category": "Best Film",
        "winner_name": "Parasite (TEST)",
        "winner_show": None,
        "movie_id": movie_id,
        "won": True,
    })
    print(f"  Award upserted: {award.get('category')} {award.get('year')}")

    awards = get_awards_for_movie(movie_id)
    assert len(awards) > 0, "No award rows returned"
    print(f"  Awards found: {len(awards)}")
    print(f"  {awards[0]['year']} {awards[0]['ceremony']} — {awards[0]['category']}")
    print("  Awards test passed")


def cleanup(movie_id: str, show_id: str, person_id: str):
    """Remove all test rows from the database."""
    print("\n=== Cleanup ===")
    _supabase.table("movies").delete().eq("id", movie_id).execute()
    _supabase.table("tv_shows").delete().eq("id", show_id).execute()
    _supabase.table("people").delete().eq("id", person_id).execute()
    print("  Test rows deleted")


if __name__ == "__main__":
    movie_id = test_movie_upsert_and_read()
    show_id = test_show_upsert_and_read()
    person_id = test_cast(movie_id)
    test_episodes(show_id)
    test_streaming(movie_id)
    test_boxoffice(movie_id)
    test_awards(movie_id)
    cleanup(movie_id, show_id, person_id)
    print("\n All DB tests passed. Phase 2 complete.")