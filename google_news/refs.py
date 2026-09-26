"""Input resolvers for /google-news/* params — ONE param per input
(tripadvisor QueryOrLinkField convention): each accepts the plain value OR a
news.google.com link carrying it, and auto-detects which form was passed.

    topic        WORLD | BUSINESS | … | HEADLINES — OR a topic / publication id
                 (CAAq…) — OR a news.google.com/topics/<id>[/sections/<id>] link
    section      a tab name ("Markets") | a section id (CAQ…) | a /sections/<id> link
    publication  a publisher domain (cnn.com) | its site URL | a publication id
                 | a news.google.com/publications/<id> link
    location     a place name ("Seattle", "Paris, France") | a place topic id | link
    author       an author id (the `authors[].id` of any article) | a topics link
    story        a story id (`story.id` of any article) | a /stories/<id> link
    article      an article id (CBMi…) | a news.google.com /read/, /articles/,
                 /rss/articles/ link

Every resolver raises ValueError with a user-facing message.
"""
import re
from urllib.parse import unquote, urlparse

from google_news import ids

GOOGLE_NEWS_HOST = "news.google.com"

# Public topic names -> the RSS section keys (HEADLINES is built, not redirected).
TOPIC_KEYS = {
    "HEADLINES": "HEADLINES", "TOP": "HEADLINES", "TOP_STORIES": "HEADLINES", "TOP_NEWS": "HEADLINES",
    "LATEST": "HEADLINES",
    "WORLD": "WORLD",
    "NATION": "NATION", "NATIONAL": "NATION", "COUNTRY": "NATION", "LOCAL_COUNTRY": "NATION",
    "BUSINESS": "BUSINESS",
    "TECHNOLOGY": "TECHNOLOGY", "TECH": "TECHNOLOGY",
    "ENTERTAINMENT": "ENTERTAINMENT",
    "SPORTS": "SPORTS", "SPORT": "SPORTS",
    "SCIENCE": "SCIENCE",
    "HEALTH": "HEALTH",
}
TOPIC_NAMES = ["HEADLINES", "WORLD", "NATION", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS", "SCIENCE",
               "HEALTH"]

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{16,}$")
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def is_link(value):
    low = (value or "").strip().lower()
    return low.startswith(("http://", "https://", "//")) or low.startswith(GOOGLE_NEWS_HOST)


def _url(value):
    value = value.strip()
    if value.startswith("//"):
        return "https:" + value
    if not value.lower().startswith("http"):
        return "https://" + value
    return value


def news_path(value):
    """A news.google.com link -> its path segments ([] for another site)."""
    parsed = urlparse(_url(value))
    host = (parsed.hostname or "").lower()
    if host != GOOGLE_NEWS_HOST:
        return None
    return [unquote(p) for p in parsed.path.split("/") if p and p != "."]


def _after(segments, marker):
    if segments and marker in segments:
        i = segments.index(marker)
        if i + 1 < len(segments):
            return segments[i + 1]
    return None


def _clean_id(value):
    value = (value or "").strip().split("?")[0].split("#")[0]
    return value if _ID_RE.match(value) else None


# ---- topics / sections -------------------------------------------------------------------------------------

def resolve_topic(value):
    """-> {"topic": KEY | id, "section": id | None}."""
    raw = (value or "").strip()
    key = TOPIC_KEYS.get(re.sub(r"[\s\-]+", "_", raw.upper()))
    if key:
        return {"topic": key, "section": None}
    if is_link(raw):
        segments = news_path(raw)
        if segments is None:
            raise ValueError("Must be a news.google.com topic link.")
        topic = _after(segments, "topics") or _after(segments, "publications")
        if not topic:
            raise ValueError("The link is not a Google News topic or publication page.")
        return {"topic": _checked_topic(topic), "section": _clean_id(_after(segments, "sections"))}
    return {"topic": _checked_topic(raw), "section": None}


def _checked_topic(value):
    topic = _clean_id(value)
    kind = ids.describe(topic or "")["kind"]
    if kind == "story":
        raise ValueError("That is a story id — use /google-news/story for full coverage.")
    if kind not in ("topic", "publication", "local"):
        raise ValueError(f"Must be one of {', '.join(TOPIC_NAMES)}, a Google News topic id (CAAq…) "
                         "or a news.google.com/topics/… link.")
    return topic


def resolve_section(value):
    """-> a section id (CAQ…) or a tab name to match (lower-cased)."""
    raw = (value or "").strip()
    if is_link(raw):
        section = _clean_id(_after(news_path(raw) or [], "sections"))
        if not section:
            raise ValueError("The link carries no /sections/<id>.")
        return section
    if raw.startswith("CAQ") and _clean_id(raw):
        return raw
    return raw.lower()


# ---- publications --------------------------------------------------------------------------------------------

def normalize_domain(value):
    host = (value or "").strip().lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def resolve_publication(value):
    """-> a publication id (built from the domain when a domain is given)."""
    raw = (value or "").strip()
    if is_link(raw):
        segments = news_path(raw)
        if segments is not None:
            pub = _clean_id(_after(segments, "publications") or _after(segments, "topics"))
            if pub and ids.describe(pub)["kind"] == "publication":
                return pub
            raise ValueError("The link is not a Google News publication page.")
        domain = normalize_domain(urlparse(_url(raw)).hostname or "")
    elif raw.startswith("CAAq"):
        if ids.describe(raw)["kind"] != "publication":
            raise ValueError("That id is not a Google News publication.")
        return raw
    else:
        domain = normalize_domain(raw.split("/")[0])
    if not _DOMAIN_RE.match(domain):
        raise ValueError("Must be a publisher domain (cnn.com), its website link, a Google News publication id "
                         "or a news.google.com/publications/… link.")
    return ids.publication_id(domain)


# ---- places / authors / stories / articles --------------------------------------------------------------------

def resolve_location(value):
    """-> a place topic id (CAAq…) or the place name to geocode."""
    raw = " ".join((value or "").split())
    if is_link(raw):
        topic = _clean_id(_after(news_path(raw) or [], "topics"))
        if not topic:
            raise ValueError("Must be a place name or a news.google.com/topics/… link.")
        return topic
    if raw.startswith("CAAq") and _clean_id(raw):
        if ids.describe(raw)["kind"] not in ("topic", "local"):
            raise ValueError("That id is not a Google News place topic.")
        return raw
    if len(raw) > 100:
        raise ValueError("A place name is at most 100 characters.")
    return raw


def resolve_author(value):
    raw = (value or "").strip()
    if is_link(raw):
        raw = _after(news_path(raw) or [], "topics") or ""
    author = _clean_id(raw)
    if not author or ids.describe(author)["kind"] != "topic":
        raise ValueError("Must be an author id (the `authors[].id` of an article) or a news.google.com/topics/… "
                         "link of an author.")
    return author


def resolve_story(value):
    raw = (value or "").strip()
    if is_link(raw):
        raw = _after(news_path(raw) or [], "stories") or ""
    story = _clean_id(raw)
    if not story or ids.describe(story)["kind"] != "story":
        raise ValueError("Must be a story id (the `story.id` of an article) or a news.google.com/stories/… link.")
    return story


def resolve_article(value):
    raw = (value or "").strip()
    if is_link(raw):
        segments = news_path(raw) or []
        raw = _after(segments, "articles") or _after(segments, "read") or ""
    article = _clean_id(raw)
    if not article or not article.startswith(("CBMi", "CAIi")):
        raise ValueError("Must be a Google News article id (CBMi…) or a news.google.com article link.")
    return article


def resolve_source(value):
    """A search `source`: a publisher domain or its website link -> domain."""
    raw = (value or "").strip()
    domain = normalize_domain(urlparse(_url(raw)).hostname or "") if is_link(raw) else normalize_domain(raw)
    if not _DOMAIN_RE.match(domain):
        raise ValueError("Must be a publisher domain (e.g. reuters.com) or its website link.")
    return domain
