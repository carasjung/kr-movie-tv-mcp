"""
Tests for data_sources/naver_tv.py
Run from project root: PYTHONPATH=. python tests/test_naver_tv.py

Note: Uses Korean titles (original broadcast titles, not English translations).
Each test opens a real browser — expect 10-20 seconds per test.
"""

from data_sources.naver_tv import (
    get_episode_ratings,
    get_ost_albums,
    get_drama_broadcast_info,
)


def test_episode_ratings_completed():
    print("\n=== Episode Ratings: 도깨비 (Goblin - completed) ===")
    result = get_episode_ratings("도깨비")
    print(f"  Found: {result['found']}")
    print(f"  Channel: {result['channel']}")
    print(f"  Latest rating: {result['latest_rating']}% (ep {result['latest_episode']})")
    print(f"  Highest rating: {result['highest_rating']}% (ep {result['highest_episode']})")
    print(f"  Episodes tracked: {result['total_episodes_tracked']}")
    print(f"  Episode breakdown:")
    for ep in result["episodes"]:
        print(f"    Ep {ep['episode']} ({ep['air_date']}): {ep['rating']}%")


def test_episode_ratings_airing():
    print("\n=== Episode Ratings: 대군부인 (Perfect Crown - airing) ===")
    result = get_episode_ratings("대군부인")
    print(f"  Found: {result['found']}")
    print(f"  Channel: {result['channel']}")
    print(f"  Latest rating: {result['latest_rating']}% (ep {result['latest_episode']})")
    print(f"  Highest rating: {result['highest_rating']}% (ep {result['highest_episode']})")
    print(f"  Episodes tracked: {result['total_episodes_tracked']}")
    for ep in result["episodes"]:
        print(f"    Ep {ep['episode']} ({ep['air_date']}): {ep['rating']}%")


def test_ost_albums():
    print("\n=== OST Albums: 도깨비 ===")
    result = get_ost_albums("도깨비")
    print(f"  Found: {result['found']}")
    print(f"  Total OST albums: {result['total_albums']}")
    for album in result["albums"][:5]:
        print(f"  {album['album_name']} — {album['artist']} ({album['release_date']})")
        print(f"    Vibe: {album['vibe_url']}")


def test_combined():
    print("\n=== Combined: 사랑의 불시착 (Crash Landing on You) ===")
    result = get_drama_broadcast_info("사랑의 불시착")
    print(f"  Channel: {result['channel']}")
    print(f"  Latest rating: {result['latest_rating']}% (ep {result['latest_episode']})")
    print(f"  Highest rating: {result['highest_rating']}% (ep {result['highest_episode']})")
    print(f"  Episodes tracked: {result['total_episodes_tracked']}")
    print(f"  OST albums: {result['total_ost_albums']}")
    for album in result["ost_albums"][:3]:
        print(f"    {album['album_name']} — {album['artist']}")


if __name__ == "__main__":
    test_episode_ratings_completed()
    test_episode_ratings_airing()
    test_ost_albums()
    test_combined()
    print("\nAll Naver TV tests complete.")