# scripts/run_sync_tmdb.py
from pipeline.jobs.sync_tmdb import sync_tmdb_flow
sync_tmdb_flow(movie_limit=200, show_limit=200)
