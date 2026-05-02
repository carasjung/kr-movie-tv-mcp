from pipeline.jobs.sync_wikipedia import sync_wikipedia_flow
sync_wikipedia_flow(skip_existing=True, limit=100)
