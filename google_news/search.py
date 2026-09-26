"""Search — over news.google.com/rss/search (validated 2026-09-26).

The HTML /search page (and its data) is a hard /sorry captcha for every
client tried: curl direct, curl over residential exits, headful patchright
Chrome direct and on a warmed residential session. The RSS feed never is.

The feed answers up to ~100 results with no pagination (num / start / page
are ignored), so the 100 are fetched once, cached, sorted and paged in memory.
Operators Google honours inside q (all verified): `when:1h|1d|7d|30d|1y`,
`after:YYYY-MM-DD`, `before:YYYY-MM-DD`, `site:<domain>`, `intitle:"…"`,
`"exact phrase"`, `-exclude`, `OR`. (`allintitle:` answers nothing; `when:1m`
/ `when:12m` answer nothing — months are 30d / 1y.)

RSS items carry no image / author / publisher id; the publisher article URL
is decoded per item (articles.resolve_many) when resolve_links is on — only
for the page being returned.
"""
from urllib.parse import urlencode
from xml.etree import ElementTree

from google_news import articles as article_links
from google_news import cache_config as ttl
from google_news import fetch, parsers
from google_news.editions import edition as get_edition
from google_news.shared import page_slice

SITE = fetch.SITE

TIME_WINDOWS = {"past_hour": "1h", "past_day": "1d", "past_week": "7d", "past_month": "30d", "past_year": "1y",
                "anytime": None}


def build_query(query, time_published=None, from_date=None, to_date=None, source=None, in_title=False):
    """The public params -> Google's q with operators."""
    q = query
    if in_title:
        q = f'intitle:"{query}"' if " " in query and not query.startswith('"') else f"intitle:{query}"
    when = TIME_WINDOWS.get(time_published or "anytime")
    if when:
        q += f" when:{when}"
    if from_date:
        q += f" after:{from_date}"
    if to_date:
        q += f" before:{to_date}"
    if source:
        q += f" site:{source}"
    return q


def _search_feed(q, ed):
    def build():
        url = f"{SITE}/rss/search?{urlencode({'q': q, **ed.query()})}"
        text = fetch.get_text(url, label="search")
        try:
            _title, items = parsers.parse_rss(text, ed)
        except ElementTree.ParseError:
            fetch.dump_debug("search_badrss", text)
            raise fetch.NewsUpstreamError("search: the feed is not valid RSS")
        return items

    return fetch.dataset("search", {"q": q, "edition": ed.ceid}, build, ttl.SEARCH_CACHE)


def search(query, edition, time_published=None, from_date=None, to_date=None, source=None, in_title=False,
           sort="relevance", resolve_links=True, page=1):
    """News articles matching a query (up to ~100, 20 per page)."""
    ed = get_edition(edition)
    q = build_query(query, time_published, from_date, to_date, source, in_title)
    items = list(_search_feed(q, ed))
    if sort == "newest":
        items.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda a: a.get("published_at") or "9999")
    page_items, pagination = page_slice(items, page)
    if resolve_links:
        article_links.resolve_many(page_items)
    return {"query": query, "google_query": q, "articles": page_items, "edition": ed.summary(),
            "pagination": pagination}
