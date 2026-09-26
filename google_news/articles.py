"""Article id -> the publisher's URL (validated 2026-09-26).

The id (CBMi…) is an opaque protobuf (the base64 shortcut died in 2024).
The site's own decoder: GET news.google.com/rss/articles/<id> (the smallest
of the three article pages, ~600 KB, gzip on the wire) carries a per-article
signature `data-n-a-sg` + timestamp `data-n-a-ts`; the DotsSplashUi rpc
Fbv4je (garturlreq) with that pair answers
["garturlres", <canonical URL>, 1, <AMP URL>]. A signature only unlocks its
own article. A decoded link never changes, so it is cached for 30 days.
"""
from google_news import cache_config as ttl
from google_news import fetch, parsers
from google_search.news import _SIG_RE

SITE = fetch.SITE

# The request context garturlreq carries (the site sends placeholders).
_GARTURL_CTX = [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0]


def _decode(article):
    page = fetch.get_text(f"{SITE}/rss/articles/{article}", label="article page")
    m = _SIG_RE.search(page)
    if not m:
        fetch.dump_debug("article_nosig", page)
        raise fetch.NewsNotFound(f"Google News has no article {article!r}.")
    sg, ts = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    ts = int(ts) if str(ts).isdigit() else ts
    data = fetch.rpc("Fbv4je", ["garturlreq", _GARTURL_CTX, article, ts, sg], label="article link",
                     not_found=f"Google News has no article {article!r}.")
    link = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], str) else None
    amp = data[3] if isinstance(data, list) and len(data) > 3 and isinstance(data[3], str) else None
    if not link:
        fetch.dump_debug("article_nolink", repr(data))
        raise fetch.NewsUpstreamError("Google News did not return the article URL.")
    return {"link": link, "amp_link": amp if amp and amp != link else None}


def decoded(article):
    """{link, amp_link} for one article id (cached)."""
    return fetch.dataset("article_link", {"article": article}, lambda: _decode(article), ttl.RESOLVE_CACHE)


def resolve(article):
    """The /google-news/article/resolve endpoint."""
    links = decoded(article)
    return {"id": article, "link": links["link"], "amp_link": links["amp_link"],
            "google_link": parsers.article_google_link(article)}


def resolve_many(articles):
    """Fill `link` / `amp_link` in place on article dicts (and their
    related_articles) whose link is unknown. A failed decode leaves the
    link null rather than failing the whole page."""
    import config
    todo = []
    for a in articles:
        for item in [a] + list(a.get("related_articles") or []):
            if item.get("id") and not item.get("link"):
                todo.append(item)
    if not todo:
        return articles

    def one(item):
        try:
            return decoded(item["id"])
        except (fetch.NewsNotFound, fetch.NewsUpstreamError):
            return None

    results = fetch.run_parallel([lambda item=item: one(item) for item in todo],
                                 workers=max(1, int(config.GOOGLE_NEWS_RESOLVE_WORKERS)))
    for item, links in zip(todo, results):
        if links:
            item["link"], item["amp_link"] = links["link"], links["amp_link"]
    return articles
