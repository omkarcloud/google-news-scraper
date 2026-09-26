"""Cache TTLs for /google-news/* (cache.py, keyed on the validated params —
marshmallow resolves every one-param input first, so `topic=WORLD`, the
topic id and a news.google.com/topics link share a row, and `country=us`
/ `country=US&language=en` share one too).

Feeds are cached WHOLE (google_news/fetch.dataset: in-process memo + the
shared cache) and paged in memory, so every page of a feed comes from one
upstream call. Google refreshes headlines every few minutes; ids, editions,
topic menus and decoded article links barely change."""
from datetime import timedelta

FEED_CACHE = timedelta(minutes=10)          # headlines / topic / section / local / publication / author feeds
SEARCH_CACHE = timedelta(minutes=15)
STORY_CACHE = timedelta(minutes=15)
HOME_CACHE = timedelta(minutes=10)
SHOWCASE_CACHE = timedelta(hours=1)
TOPIC_CACHE = timedelta(days=1)             # nav menu, topic info + section tabs
ID_CACHE = timedelta(days=7)                # topic name / place name -> topic id
RESOLVE_CACHE = timedelta(days=30)          # article id -> publisher URL (never changes)
AUTOCOMPLETE_CACHE = timedelta(days=1)
