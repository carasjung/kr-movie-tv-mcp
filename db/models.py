"""
db/models.py — Table definitions and field documentation.

This file serves as the source of truth for what each table stores
and which source each field comes from. It does not interact with
the database directly — that's db/queries.py.

Field naming convention:
    Fields are named by source to avoid ambiguity:
    tmdb_rating         = TMDB global community score
    mdl_rating          = MyDramaList community score
    naver_audience_rating = Naver verified ticket buyers
    rt_tomatometer      = Rotten Tomatoes critic score
"""

# ── Table field references ─────────────────────────────────────────────────────
# These dicts define the canonical fields for upsert operations.
# Keys match the Supabase column names exactly.

MOVIE_FIELDS = {
    # Cross-source IDs
    "tmdb_id":                  "str  | TMDB movie ID",
    "kobis_movie_code":         "str  | KOBIS Korean film registry code",
    "kmdb_id":                  "str  | KMDb Korean Movie Database ID",
    "naver_slug":               "str  | Naver movie search slug",
    "justwatch_slug":           "str  | JustWatch URL slug",
    "hancinema_slug":           "str  | HanCinema page slug",
    "wikipedia_title":          "str  | Wikipedia article title",

    # Titles
    "title_english":            "str  | English title (required)",
    "title_korean":             "str  | Korean title (한글)",
    "title_romanized":          "str  | Romanized Korean title",

    # Content
    "synopsis_short":           "str  | Short synopsis (TMDB overview)",
    "synopsis_full":            "str  | Full synopsis (Wikipedia Plot section)",

    # Metadata
    "release_year":             "int  | 4-digit release year",
    "release_date":             "date | Full release date",
    "runtime_minutes":          "int  | Runtime in minutes",
    "genres":                   "list | Genre list (TMDB)",
    "status":                   "str  | Released / In Production etc.",
    "age_rating":               "str  | MPAA or Korean rating",
    "country":                  "str  | Production country",
    "poster_url":               "str  | Poster image URL",

    # Ratings — clearly labeled by source and audience type
    "tmdb_rating":              "float| TMDB global community score (0-10)",
    "naver_audience_rating":    "float| Naver verified Korean ticket buyers (0-10)",
    "naver_netizen_rating":     "float| Naver Korean general public (0-10)",
    "rt_tomatometer":           "int  | RT Western professional critics (0-100%)",
    "rt_audience_score":        "int  | RT Western general public (0-100%)",
    "rt_critics_rating":        "str  | Certified Fresh / Fresh / Rotten",

    # Box office
    "kobis_cumulative_audience":"int  | Total Korean admissions (KOBIS)",

    # JSON blobs
    "wiki_sections":            "json | Wikipedia sections dict {name: content}",
}

SHOW_FIELDS = {
    # Cross-source IDs
    "tmdb_id":                  "str  | TMDB TV show ID",
    "mdl_id":                   "str  | MyDramaList show ID",
    "mdl_slug":                 "str  | MyDramaList URL slug",
    "naver_show_id":            "str  | Naver OS parameter (show ID)",
    "justwatch_slug":           "str  | JustWatch URL slug",
    "hancinema_slug":           "str  | HanCinema page slug",
    "wikipedia_title":          "str  | Wikipedia article title",

    # Titles
    "title_english":            "str  | English title (required)",
    "title_korean":             "str  | Korean title (한글)",
    "title_romanized":          "str  | Romanized Korean title",

    # Content
    "synopsis_short":           "str  | Short synopsis (TMDB/MDL overview)",
    "synopsis_full":            "str  | Full synopsis (Wikipedia)",

    # Metadata
    "year":                     "int  | Premiere year",
    "first_air_date":           "date | First episode air date",
    "last_air_date":            "date | Final episode air date",
    "status":                   "str  | Airing / Ended / Upcoming",
    "total_episodes":           "int  | Total episode count",
    "genres":                   "list | Genre list",
    "tags":                     "list | MDL community tags",
    "network":                  "str  | Broadcast network (tvN, KBS, Netflix etc.)",
    "content_type":             "str  | Korean Drama / Korean Movie etc.",
    "age_rating":               "str  | Content rating",
    "poster_url":               "str  | Poster image URL",

    # Ratings — clearly labeled by source and audience type
    "tmdb_rating":              "float| TMDB global community score (0-10)",
    "mdl_rating":               "float| MyDramaList international K-drama fans (0-10)",
    "naver_latest_rating":      "float| Nielsen Korea latest episode rating (%)",
    "naver_highest_rating":     "float| Nielsen Korea peak episode rating (%)",
    "naver_latest_episode":     "int  | Most recent tracked episode number",

    # JSON blobs
    "wiki_sections":            "json | Wikipedia sections dict {name: content}",
}

PERSON_FIELDS = {
    "tmdb_person_id":           "str  | TMDB person ID",
    "name_english":             "str  | English name (required)",
    "name_korean":              "str  | Korean name",
    "known_for_department":     "str  | Acting / Directing",
    "profile_url":              "str  | Profile photo URL",
}

EPISODE_FIELDS = {
    "show_id":                  "uuid | Foreign key to tv_shows",
    "episode_number":           "int  | Episode number (1-based)",
    "air_date":                 "date | Air date (MM.DD. from Naver)",
    "nielsen_rating":           "float| Nielsen Korea viewership % (e.g. 20.5)",
    "channel":                  "str  | Broadcast channel (tvN, MBC etc.)",
}

STREAMING_FIELDS = {
    "movie_id":                 "uuid | FK to movies (null for shows)",
    "show_id":                  "uuid | FK to tv_shows (null for movies)",
    "region":                   "str  | ISO region code (us, uk, ca, au, kr)",
    "provider":                 "str  | Provider name (Netflix, Viki etc.)",
    "monetization_type":        "str  | Subscription / Rent / Buy / Free",
    "quality":                  "str  | 4K / HD / SD",
    "price":                    "str  | Price string (e.g. $3.99 / month)",
    "watch_url":                "str  | Direct watch URL",
    "provider_logo_url":        "str  | Provider logo image URL",
}

AWARD_FIELDS = {
    "ceremony":                 "str  | Award ceremony name",
    "year":                     "int  | Award year",
    "category":                 "str  | Award category",
    "winner_name":              "str  | Winner person or title",
    "winner_show":              "str  | Winner show title",
    "movie_id":                 "uuid | FK to movies (if applicable)",
    "show_id":                  "uuid | FK to tv_shows (if applicable)",
    "won":                      "bool | True = winner, False = nominee",
}

BOXOFFICE_FIELDS = {
    "kobis_movie_code":         "str  | KOBIS movie code",
    "movie_id":                 "uuid | FK to movies",
    "week_start":               "date | Week start date",
    "period_type":              "str  | weekly / weekend / daily",
    "rank":                     "int  | Box office rank",
    "audience_count":           "int  | Admissions for this period",
    "sales_amount":             "int  | Sales in KRW",
    "sales_share":              "float| % of total market",
    "screen_count":             "int  | Number of screens",
}