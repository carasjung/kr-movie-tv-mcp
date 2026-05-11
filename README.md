# Korean Entertainment MCP Server

A production-grade MCP (Model Context Protocol) server for Korean movies and TV shows, built from 10 data sources and deployed with OAuth 2.1 authentication via Descope.

**Live endpoint:** `https://kr-movie-tv-mcp-production.up.railway.app/mcp`

---

## What This Does

The server exposes 17 tools that let AI agents query a unified Korean entertainment database — combining data that previously required visiting 6+ separate websites:

- Korean and international ratings (Nielsen Korea, Naver, MDL, TMDB, Rotten Tomatoes)
- Per-episode Nielsen Korea viewership trajectories
- JustWatch streaming availability across US/UK/CA/AU
- KOBIS official Korean box office rankings
- Award history across 5 major Korean ceremonies
- OST albums with Naver Vibe links
- Cast filmographies with Korean name lookup

---

## MCP Tools

### Discovery
| Tool | Description |
|---|---|
| `search_titles` | Search movies and dramas by English or Korean title |
| `get_trending_dramas` | Currently airing dramas sorted by MDL rating |
| `get_top_dramas` | All-time best completed dramas, filterable by genre |
| `get_top_movies` | Best Korean films, filterable by genre/year/rating |
| `browse_by_genre` | Filter by genre for movies or dramas |
| `browse_by_tag` | Filter dramas by MDL community tags (Bromance, Time Travel, Revenge, etc.) |

### Detail
| Tool | Description |
|---|---|
| `get_movie` | Full movie details with all 5 rating sources |
| `get_drama` | Full drama details with all rating sources |
| `get_cast` | Cast list with character names and role types |
| `get_episode_ratings` | Nielsen Korea per-episode viewership % |
| `get_ost_albums` | OST albums with Naver Vibe streaming links |

### Utility
| Tool | Description |
|---|---|
| `find_where_to_watch` | Streaming availability by title + region |
| `find_by_provider` | All Korean content on Netflix/Viki/etc. in a region |
| `get_weekly_boxoffice` | KOBIS Korean box office rankings |
| `get_actor_filmography` | Full filmography for an actor or director |
| `get_awards` | Award history for a title or full ceremony year |
| `compare_ratings` | Side-by-side rating comparison across all sources |

---

## Data Sources

### 1. TMDB — Official API
Core metadata for all Korean movies and TV shows — titles, cast, genres, ratings, poster images. Seeds the database with ~9,983 movies and ~3,500+ shows.

### 2. KOBIS (Korean Film Council) — Official API
Official Korean weekly and daily box office rankings, cumulative admissions, sales revenue, screen counts. The only source for authoritative Korean theatrical data.

### 3. MyDramaList — Web Scraper (Playwright)
Community ratings, episode counts, airing status, and uniquely: community-generated tags ("Bromance", "Time Travel", "CEO Male Lead"). No other source has structured K-drama tags.

### 4. HanCinema — Web Scraper (Playwright)
Historical Korean film and drama metadata, including older content not covered by TMDB.

### 5. Naver Movies — Web Scraper (Playwright)
Two unique Korean-audience ratings for films:
- **실관람객 평점** (Verified ticket buyer rating) — linked to actual cinema purchases
- **네티즌 평점** (Netizen rating) — Korean general public

### 6. Naver TV — Web Scraper (Playwright)
Per-episode Nielsen Korea viewership ratings extracted from SVG chart elements. No English-language source has this data. Also scrapes OST albums from Naver Vibe.

### 7. JustWatch — Web Scraper (Playwright)
Where-to-watch data across 364+ providers in US, UK, CA, AU — including monetization type, price, and quality.

### 8. Wikipedia — Official REST API
Plot summaries, production background, critical reception sections. Section alias system handles non-standard article names.

### 9. Awards — Web Scrapers (httpx + Playwright)
Five major Korean award ceremonies:
- KBS, MBC, SBS Drama Awards (from AsianWiki)
- Blue Dragon Film Awards + Blue Dragon Series Awards (OTT)
- Baeksang Arts Awards (from official site)

### 10. KMDb — Pending API approval

---

## Database Schema

Built on **Supabase** (PostgreSQL), free tier.

### 11 Tables

| Table | Description |
|---|---|
| `movies` | ~9,983 Korean films with all cross-source IDs and ratings |
| `tv_shows` | ~3,500+ Korean dramas with MDL/Naver/TMDB data |
| `people` | Actors and directors (shared lookup) |
| `movie_cast` | Movie-person relationships |
| `show_cast` | Show-person relationships |
| `episodes` | Per-episode Nielsen Korea ratings |
| `ost_albums` | Drama OST albums with Vibe links |
| `awards` | Award winners across 5 ceremonies |
| `award_nominees` | Nominees per award category |
| `streaming_availability` | Per title/region/provider streaming rows |
| `boxoffice` | Weekly KOBIS box office data |

### Rating Field Naming Convention

All rating fields are explicitly named by source:

```sql
tmdb_rating              -- Global community (0-10)
mdl_rating               -- International K-drama fans (0-10)
naver_audience_rating    -- Korean verified ticket buyers (0-10)
naver_netizen_rating     -- Korean general public (0-10)
naver_latest_rating      -- Nielsen Korea latest episode (%)
naver_highest_rating     -- Nielsen Korea peak episode (%)
rt_tomatometer           -- Western professional critics (0-100%)
rt_audience_score        -- Western RT users (0-100%)
```

---

## Architecture

```
GitHub Actions (scheduling)
    ↓
Prefect flows (retry logic, task caching, logging)
    ↓
data_sources/* (Playwright + httpx + REST APIs)
    ↓
pipeline/utils.py (data normalization)
    ↓
db/queries.py (upsert operations)
    ↓
Supabase (PostgreSQL + PostgREST)
    ↓
server.py (FastMCP + Descope OAuth 2.1)
    ↓
Railway (always-on hosting)
```

### Sync Schedules

| Job | Schedule | What it syncs |
|---|---|---|
| `sync_tmdb` | Nightly 2am UTC | New Korean titles, rating updates |
| `sync_mydramalist` | Nightly 3am UTC | Airing status, MDL ratings, tags |
| `sync_naver_tv` | Nightly 4am UTC | Episode ratings for airing shows |
| `sync_kobis` | Weekly Monday | Korean box office |
| `sync_justwatch` | Weekly Wednesday | Streaming availability (200 titles) |
| `sync_wikipedia` | Weekly Thursday | Plot summaries (new titles only) |
| `sync_awards` | Weekly Sunday | Award ceremony data |

---

## Repository Structure

```
kr-movie-tv-mcp/
├── data_sources/          # One file per data source
│   ├── tmdb.py
│   ├── kobis.py
│   ├── mydramalist.py
│   ├── hancinema.py
│   ├── naver.py
│   ├── naver_tv.py
│   ├── justwatch.py
│   ├── wikipedia.py
│   └── awards.py
├── db/
│   ├── models.py          # Field documentation
│   └── queries.py         # All DB read/write operations
├── pipeline/
│   ├── utils.py           # Shared helpers
│   ├── orchestrator.py    # Master flow
│   └── jobs/              # One sync job per source
├── scripts/               # GitHub Actions runner scripts
├── tests/                 # One test file per data source
├── .github/workflows/
│   ├── nightly.yml
│   ├── weekly.yml
│   └── initial_population.yml
├── server.py              # FastMCP MCP server
├── schema.sql             # Full Supabase schema
├── railway.toml           # Railway deployment config
└── requirements.txt
```

---

## Deployment

### MCP Server
- **Hosting:** Railway ($5/month, always-on)
- **Auth:** Descope OAuth 2.1 via FastMCP `DescopeProvider`
- **Transport:** Streamable HTTP
- **Endpoint:** `https://kr-movie-tv-mcp-production.up.railway.app/mcp`

### Pipeline
- **Scheduling:** GitHub Actions (2,000 free min/month)
- **Orchestration:** Prefect (retry logic, task caching)
- **Database:** Supabase free tier (500MB, unlimited API requests)

---

## Environment Variables

```bash
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Pipeline sources
TMDB_API_KEY=
KOBIS_API_KEY=

# Descope auth (for MCP server)
DESCOPE_CONFIG_URL=    # .well-known URL from Descope console
SERVER_URL=            # Railway public URL
```

---

## Connecting to Claude

1. Go to claude.ai → Settings → Connectors
2. Click **Add custom connector**
3. Paste: `https://kr-movie-tv-mcp-production.up.railway.app/mcp`
4. Complete the Descope OAuth flow

---

## Known Limitations

- **Rotten Tomatoes:** Package breaks when RT changes HTML. Currently excluded.
- **Korean streaming platforms (TVING, Wavve, Coupang):** Require Korean phone number. Excluded.
- **KMDb:** API membership pending approval.
- **JustWatch initial population:** ~85 seconds per title across 4 regions. Weekly sync adds 200 titles at a time.
- **TV shows:** ~3,500 of ~10,000 synced (GitHub Actions 6-hour timeout during initial population). Nightly sync continues filling gaps.
- **Airing status:** Shows added before MDL sync completed may have incorrect status. Resolves over time.

---

## Phase Status

| Phase | Status |
|---|---|
| Phase 1: Data Sources (10 sources) | ✅ Complete |
| Phase 2: Database Schema (11 tables) | ✅ Complete |
| Phase 3: Pipeline Jobs + GitHub Actions | ✅ Complete |
| Phase 4: MCP Server (FastMCP + Descope + Railway) | ✅ Complete |
| Phase 5: Marketplace Listing | 🔄 In Progress |