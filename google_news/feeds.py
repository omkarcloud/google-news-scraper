"""Article feeds — every one is the gtsreq rpc (EAfJqe) on a topic id:

  top headlines        the Headlines topic (/m/05jhg) of the edition
  topic articles       a standard topic, any topic id, optionally one section tab
  local headlines      the place topic Google geocodes a place name to
  publication articles a publication id (built from a domain) + its tab
  author articles      an author topic id (from any article's authors[].id)
  home                 gbreq: "Your briefing" (Top stories + Picks for you)
  showcase             ggctreq: News Showcase panels

A feed is ~50-70 entries (story clusters and lone articles); it is fetched
once, cached whole (fetch.dataset) and paged in memory. Each entry is the
lead article with its `story` and the story's `related_articles`.
Pagination beyond the first answer does not exist upstream: the gtsreq
continuation slot never carries a token.
"""
from google_news import cache_config as ttl
from google_news import catalog, fetch, parsers
from google_news.editions import edition as get_edition
from google_news.shared import PER_PAGE, page_slice

SHOWCASE_PER_PAGE = 10


def _articles(topic, section, ed):
    """The whole feed of one topic id (+ section id) in one edition."""
    def build():
        data = fetch.rpc("EAfJqe", ["gtsreq", ed.context(), section, topic, ""], hl=ed.hl, gl=ed.country,
                         label="articles", not_found="Google News has no articles for this topic.")
        return parsers.parse_feed(data, ed)

    return fetch.dataset("articles", {"topic": topic, "section": section, "edition": ed.ceid}, build,
                         ttl.FEED_CACHE)


def _topic_summary(info):
    return {"id": info["id"], "name": info.get("name"), "type": info.get("type"),
            "google_link": info.get("google_link")}


def _section_summary(tab):
    return {"id": tab["id"], "name": tab.get("name"), "google_link": tab.get("google_link")} if tab else None


def _feed(topic, section, ed, page, head_key="topic", head=None):
    info = catalog.topic_info(topic, ed)
    tab = catalog.match_section(info, section)
    articles = _articles(topic, tab["id"] if tab else None, ed)
    items, pagination = page_slice(articles, page)
    out = {head_key: head(info) if head else _topic_summary(info), "section": _section_summary(tab),
           "articles": items, "edition": ed.summary(), "pagination": pagination}
    return out


def top_headlines(edition, page=1):
    """The edition's Headlines: ~70 top stories, each with its related coverage."""
    ed = get_edition(edition)
    return _feed(catalog.topic_id("HEADLINES", ed), None, ed, page)


def topic_articles(topic, edition, section=None, page=1):
    """A topic's articles (WORLD, BUSINESS, … or any topic id), optionally
    one section tab (Markets, NFL, …)."""
    ed = get_edition(edition)
    out = _feed(catalog.topic_id(topic, ed), section, ed, page)
    if topic in catalog.TOPIC_NAMES:
        out["topic"]["key"] = topic
    return out


def local_headlines(location, edition, page=1):
    """Local news for a place (city, region or country name, or a place
    topic id / link)."""
    ed = get_edition(edition)
    return _feed(catalog.place_id(location, ed), None, ed, page, head_key="location", head=_place_head)


def _place_head(info):
    return {"id": info["id"], "name": info.get("name"), "google_link": info.get("google_link"),
            "image": info.get("image")}


def _publication_head(info):
    return {"id": info["id"], "name": info.get("name"), "domain": info.get("domain"),
            "google_link": info.get("google_link"), "icon": info.get("image")}


def publication_articles(publication, edition, section=None, page=1):
    """A publisher's latest articles on Google News (its "Recent" tab), or
    its News Showcase tab with section=showcase."""
    ed = get_edition(edition)
    return _feed(publication, section, ed, page, head_key="publication", head=_publication_head)


def _author_head(info):
    return {"id": info["id"], "name": info.get("name"), "google_link": info.get("google_link"),
            "image": info.get("image"), "initials": info.get("initials")}


def author_articles(author, edition, page=1):
    """A journalist's latest articles (the author id comes from any
    article's authors[].id)."""
    ed = get_edition(edition)
    return _feed(author, None, ed, page, head_key="author", head=_author_head)


def home(edition):
    """The edition's front page ("Your briefing"): the top stories and
    Google's picks, with the link to the full Headlines."""
    ed = get_edition(edition)

    def build():
        data = fetch.rpc("Giukpf", ["gbreq", ed.context()], hl=ed.hl, gl=ed.country, label="home")
        return parsers.parse_home(data, ed)

    out = dict(fetch.dataset("home", {"edition": ed.ceid}, build, ttl.HOME_CACHE))
    out["edition"] = ed.summary()
    return out


def showcase(edition, page=1):
    """News Showcase: publisher-curated panels (logo, tagline, 3+ stories)."""
    ed = get_edition(edition)

    def build():
        data = fetch.rpc("l99YQ", ["ggctreq", ed.context(), ""], hl=ed.hl, gl=ed.country, label="showcase")
        return parsers.parse_showcase(data, ed)

    panels = fetch.dataset("showcase", {"edition": ed.ceid}, build, ttl.SHOWCASE_CACHE)
    items, pagination = page_slice(panels, page, SHOWCASE_PER_PAGE)
    return {"panels": items, "edition": ed.summary(), "pagination": pagination}


__all__ = ["top_headlines", "topic_articles", "local_headlines", "publication_articles", "author_articles",
           "home", "showcase", "PER_PAGE"]
