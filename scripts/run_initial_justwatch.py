from pipeline.jobs.sync_justwatch import sync_justwatch_flow
# Only sync the most important titles initially — top rated movies and shows
sync_justwatch_flow(sync_movies=True, sync_shows=True, limit=100)