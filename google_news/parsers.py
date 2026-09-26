"""Positional-array parsers for the Google News rpc replies and the RSS
feed. Every parser takes the decoded rpc `data` and never raises on a
partial or reshaped payload (missing slots become null / []).

Article node (the same everywhere, `node[0] == 13`), validated 2026-09-26:
  [1][1]    article id (CBMi…)              [2]  title
  [3]       snippet (story pages only)      [4][0] published, unix seconds
  [6]/[38]  publisher URL                   [40] AMP URL
  [8][0]    image: [0] "/attachments/<id>", [2] width, [3] height, [5] attachment id, [13] original URL
  [10]      publisher: [2] name, [3][0] favicon (…faviconV2?url=<homepage>…)
  [36][1]   "Go to …" links: publications/<publication id>, topics/<author topic id>
  [42][0][4] "channel_story_360:<story id>"   [47][14] story id (cluster siblings)
  [46]      label ("Opinion")                [47][9][0] kicker ("LETTER TO THE EDITOR")
  [51]      authors [[name], …]
Cluster (a story on a feed): [0] lead node, [1] [[sibling node], …],
  [2] story id, [3] "Full Coverage of this story", [8] story title.

Skipped on purpose: [7] (a second copy of the URL on some nodes), [34]
("7 minutes ago", presentation), [42] tracking / ranking blobs, [44]/[49]/
[50]/[53] unlabelled UI flags, colours, the "Panoptic Response ID" tracking
string, the publisher's `PublisherOf<id>` key.
"""
import re
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlencode, urlparse
from xml.etree import ElementTree

from google_news import ids
from google_search.news import _related, _split_title, article_id as rss_article_id  # noqa: F401
from google_search.shared import at, clean_text, iso_from_ts, to_int

SITE = "https://news.google.com"
_STORY_PREFIX = "channel_story_360:"

# Nav-menu icons -> the stable topic keys (the names are localised).
NAV_ICON_KEYS = {
    "flag": "NATION", "public": "WORLD", "room": "LOCAL", "business": "BUSINESS", "memory": "TECHNOLOGY",
    "theaters": "ENTERTAINMENT", "directions_bike": "SPORTS", "experiment": "SCIENCE",
    "fitness_center": "HEALTH",
}


# ---- links ---------------------------------------------------------------------------------------------

def google_link(path, edition=None):
    """news.google.com/<path> with the edition's hl/gl/ceid query."""
    if not path:
        return None
    link = f"{SITE}/{path.lstrip('./')}"
    return f"{link}?{urlencode(edition.query(), safe=':')}" if edition is not None else link


def article_google_link(article, edition=None):
    return google_link(f"read/{article}", edition) if article else None


def story_google_link(story, edition=None):
    return google_link(f"stories/{story}", edition) if story else None


def topic_google_link(topic, edition=None, section=None):
    if not topic:
        return None
    kind = ids.describe(topic)["kind"]
    base = "publications" if kind == "publication" else "topics"
    path = f"{base}/{topic}" + (f"/sections/{section}" if section else "")
    return google_link(path, edition)


def attachment_link(attachment):
    """Google's image proxy for an attachment id (serves the full image)."""
    return f"{SITE}/api/attachments/{attachment}" if attachment else None


def _str(value):
    return value if isinstance(value, str) and value.strip() else None


def _http(value):
    return value if isinstance(value, str) and value.startswith(("http://", "https://")) else None


def _homepage_from_favicon(favicon):
    """faviconV2?url=https://www.bbc.com&… -> https://www.bbc.com"""
    if not favicon:
        return None
    try:
        url = parse_qs(urlparse(favicon).query).get("url", [None])[0]
    except ValueError:
        return None
    return _http(url)


def _host(link):
    try:
        host = (urlparse(link).hostname or "").lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else (host or None)


# ---- article node --------------------------------------------------------------------------------------

def is_article(node):
    return (isinstance(node, list) and len(node) > 6 and node[0] == 13 and isinstance(node[1], list)
            and len(node[1]) > 1 and node[1][0] == 13 and isinstance(node[1][1], str))


def is_cluster(node):
    return (isinstance(node, list) and len(node) > 3 and is_article(node[0]) and isinstance(node[2], str)
            and node[2].startswith("CAAq"))


def parse_image(raw):
    if not isinstance(raw, list):
        return None
    original = _http(at(raw, 13))
    proxy = at(raw, 0)
    attachment = _str(at(raw, 5)) or (proxy.rsplit("/", 1)[-1] if isinstance(proxy, str) and "/attachments/" in proxy
                                      else None)
    if not original and not attachment:
        return None
    return {
        "link": original or attachment_link(attachment),
        "google_link": attachment_link(attachment),
        "width": to_int(at(raw, 2)),
        "height": to_int(at(raw, 3)),
    }


def _go_to_links(node):
    """The "Go to …" links: (label without "Go to ", path)."""
    out = []
    for row in at(node, 36, 1) or []:
        label, path = at(row, 0), at(row, 1)
        if isinstance(label, str) and isinstance(path, str):
            out.append((re.sub(r"^Go to\s+", "", label).strip(), path))
    return out


def parse_publisher(node, edition=None):
    raw = at(node, 10) or []
    name = clean_text(at(raw, 2))
    favicon = _http(at(raw, 3, 0))
    publication = None
    for _label, path in _go_to_links(node):
        if path.startswith("publications/"):
            publication = path.split("/", 1)[1].split("?")[0]
            break
    homepage = _homepage_from_favicon(favicon)
    if not name and not publication:
        return None
    return {
        "id": publication,
        "name": name,
        "domain": ids.publication_domain(publication) if publication else _host(homepage),
        "link": homepage,
        "google_link": topic_google_link(publication, edition) if publication else None,
        "icon": favicon,
    }


def parse_authors(node, edition=None):
    names = [clean_text(at(row, 0)) for row in at(node, 51) or [] if isinstance(row, list)]
    topics = {label: path.split("/", 1)[1].split("?")[0] for label, path in _go_to_links(node)
              if path.startswith("topics/")}
    out = []
    for name in names:
        if not name:
            continue
        topic = topics.get(name)
        out.append({"id": topic, "name": name, "google_link": topic_google_link(topic, edition) if topic else None})
    return out


def node_story_id(node):
    for row in at(node, 42) or []:
        tag = at(row, 4)
        if isinstance(tag, str) and tag.startswith(_STORY_PREFIX):
            return tag[len(_STORY_PREFIX):] or None
    sibling = at(node, 47, 14)
    return sibling if isinstance(sibling, str) and sibling.startswith("CAAq") else None


def parse_article(node, edition=None):
    """One article node -> the public article object."""
    article = at(node, 1, 1)
    link = _http(at(node, 6)) or _http(at(node, 38))
    return {
        "id": article,
        "title": clean_text(at(node, 2)),
        "link": link,
        "amp_link": _http(at(node, 40)),
        "google_link": article_google_link(article, edition),
        "snippet": clean_text(at(node, 3)) if isinstance(at(node, 3), str) else None,
        "label": clean_text(at(node, 46)) if isinstance(at(node, 46), str) else None,
        "kicker": clean_text(at(node, 47, 9, 0)) if isinstance(at(node, 47, 9, 0), str) else None,
        "published_at": iso_from_ts(at(node, 4, 0)),
        "image": parse_image(at(node, 8, 0)),
        "publisher": parse_publisher(node, edition),
        "authors": parse_authors(node, edition),
    }


def _story_ref(story, title, edition):
    if not story:
        return None
    return {"id": story, "title": clean_text(title) if isinstance(title, str) else None,
            "google_link": story_google_link(story, edition)}


# ---- feeds (topic / section / publication / place / author / home) -------------------------------------

def _walk(obj, out):
    if is_article(obj):
        out.append(("article", obj))
    elif is_cluster(obj):
        out.append(("cluster", obj))
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, out)
    return out


def parse_feed(data, edition=None):
    """Any articles payload -> [article + story + related_articles, …] in
    page order. A story cluster becomes its lead article carrying the story
    and its sibling articles; a lone article keeps its own story id (when it
    has one) and no siblings. Duplicates (an article shown twice) are dropped."""
    out, seen = [], set()
    for kind, obj in _walk(data, []):
        if kind == "cluster":
            lead = obj[0]
            siblings = [n for n in _walk(at(obj, 1) or [], []) if n[0] == "article"]
            story = _story_ref(at(obj, 2), at(obj, 8), edition)
        else:
            lead, siblings = obj, []
            story = _story_ref(node_story_id(obj), None, edition)
        item = parse_article(lead, edition)
        if not item["id"] or item["id"] in seen:
            continue
        seen.add(item["id"])
        related = []
        for _k, node in siblings:
            sub = parse_article(node, edition)
            if sub["id"] and sub["id"] not in seen:
                seen.add(sub["id"])
                related.append(sub)
        item["story"] = story
        item["related_articles"] = related
        out.append(item)
    return out


def parse_topic_info(data, edition=None):
    """gtires -> topic / publication details with its section tabs."""
    info = at(data, 1) or []
    topic = at(info, 0)
    if not isinstance(topic, str):
        return None
    described = ids.describe(topic)
    kind = described["kind"]
    image = at(info, 3) or []
    picture = _http(at(image, 0, 0))
    sections = []
    for row in at(info, 2) or []:
        section, name = at(row, 0), clean_text(at(row, 1))
        if isinstance(section, str):
            sections.append({"id": section, "name": name,
                             "google_link": topic_google_link(topic, edition, section)})
    return {
        "id": topic,
        "name": clean_text(at(info, 1)),
        "type": {"publication": "publication", "local": "local", "story": "story"}.get(kind) or (
            "person" if at(info, 5) == 126 else "topic"),
        "domain": described.get("domain"),
        "google_link": topic_google_link(topic, edition),
        "image": picture,
        "initials": clean_text(at(image, 1)) if not picture and isinstance(at(image, 1), str) else None,
        "sections": sections,
    }


def parse_nav(data, edition=None):
    """gnmres -> the edition's topic menu."""
    out = []
    for row in at(data, 1, 0) or []:
        topic, name, icon = at(row, 0), clean_text(at(row, 1)), at(row, 2)
        if not isinstance(topic, str):
            continue
        out.append({"id": topic, "key": NAV_ICON_KEYS.get(icon), "name": name,
                    "google_link": topic_google_link(topic, edition)})
    return out


def parse_home(data, edition=None):
    """gbres ("Your briefing") -> {title, date, sections: [{title, topic,
    articles}]}. Local news is empty without a signed-in location and is
    dropped when it has no articles."""
    body = at(data, 1) or []
    sections = []
    for block in body[3:] if isinstance(body, list) else []:
        if not isinstance(block, list):
            continue
        title = clean_text(at(block, 0, 1))
        if not title:
            continue
        more = None
        for part in block[1:]:
            path = at(part, 1)
            if isinstance(part, list) and isinstance(path, str) and path.startswith("topics/"):
                more = {"id": path.split("/", 1)[1].split("?")[0], "name": clean_text(at(part, 0)),
                        "google_link": google_link(path, edition)}
        articles = parse_feed(block[1:], edition)
        if not articles:
            continue
        sections.append({"title": title, "more": more, "articles": articles})
    return {
        "title": clean_text(at(body, 0, 1)),
        "date": clean_text(at(body, 0, 2)),
        "sections": sections,
    }


# ---- story full coverage -------------------------------------------------------------------------------

def parse_x_post(item):
    """A "Posts on X" entry (type 9) -> the post."""
    post = at(item, 10) or []
    author = at(post, 2) or []
    media = [_http(at(m, 0)) for m in at(post, 7) or [] if isinstance(m, list)]
    handle = _str(at(author, 0))
    return {
        "id": _str(at(post, 6)),
        "text": clean_text(at(post, 0)),
        "link": _http(at(post, 5)),
        "published_at": iso_from_ts((at(post, 1) or 0) // 1000) if isinstance(at(post, 1), (int, float)) else None,
        "author": {
            "username": handle,
            "name": clean_text(at(author, 2)),
            "link": f"https://x.com/{handle}" if handle else None,
            "avatar": _http(at(author, 1)),
        },
        "media": [m for m in media if m],
        "has_video": at(post, 10) == "Video included in post" or "video" in str(at(post, 10) or "").lower(),
    }


def _group_type(key):
    """NEWS_EXPLAINER_RESULT_GROUP -> "explainer", TWITTER_RESULT_GROUP -> "twitter"."""
    key = re.sub(r"^NEWS_", "", key)
    key = re.sub(r"_RESULT_GROUP$", "", key)
    return key.lower() or None


def _group_items(group, edition, seen):
    articles, posts = [], []
    for item in at(group, 3) or []:
        if not isinstance(item, list):
            continue
        if item and item[0] == 9:
            posts.append(parse_x_post(item))
        elif is_article(at(item, 3)):
            a = parse_article(item[3], edition)
            if a["id"] and a["id"] not in seen:
                seen.add(a["id"])
                articles.append(a)
    return articles, posts


def parse_story(data, edition=None):
    """waaeffpresp -> {id, title, top_articles, x_posts, sections, articles}.
    Children of the "Overview" tab: type 2 = a titled group ("Top news",
    "Posts on X", "Interviews", …), type 5 = the "All coverage" header,
    type 3 = one article of the running list, type 34 = the section index."""
    header = at(data, 2, 0) or []
    overview = at(data, 2, 1) or []
    story = at(header, 1, 1)
    top, posts, sections, articles, seen = [], [], [], [], set()
    group_types = {}
    for child in at(overview, 3) or []:
        if isinstance(child, list) and child and child[0] == 34 and isinstance(at(child, 1), dict):
            for row in at(child[1], "38", 0) or []:
                name, key = clean_text(at(row, 0)), at(row, 1, 4)
                if name and isinstance(key, str):
                    group_types[name] = _group_type(key)
    for child in at(overview, 3) or []:
        if not isinstance(child, list) or not child:
            continue
        kind = child[0]
        if kind == 2:
            group = at(child, 2) or []
            title = clean_text(at(group, 2))
            group_articles, group_posts = _group_items(group, edition, seen)
            posts.extend(group_posts)
            gtype = group_types.get(title)
            if (gtype == "top_coverage" or (title or "").lower() == "top news") and not top:
                top = group_articles
            elif group_articles:
                sections.append({"title": title, "type": gtype, "articles": group_articles})
        elif kind == 3 and is_article(at(child, 3)):
            a = parse_article(child[3], edition)
            if a["id"] and a["id"] not in seen:
                seen.add(a["id"])
                articles.append(a)
    return {
        "id": story if isinstance(story, str) else None,
        "title": clean_text(at(header, 2)),
        "google_link": story_google_link(story, edition) if isinstance(story, str) else None,
        "image": _http(at(header, 17, 0, 0)),
        "top_articles": top,
        "x_posts": posts,
        "sections": sections,
        "articles": articles,
    }


# ---- News Showcase -------------------------------------------------------------------------------------

def _logo(raw):
    if not isinstance(raw, list) or not _http(at(raw, 0)):
        return None
    return {"link": at(raw, 0), "width": to_int(at(raw, 2)), "height": to_int(at(raw, 3))}


def parse_showcase(data, edition=None):
    """ggctreq -> [panel]: a publisher's curated Showcase stories."""
    out = []
    for panel in at(data, 1, 0) or []:
        head = at(panel, 0) or []
        publication = at(head, 32, 1, 1)
        domain = at(panel, 1, 13, 0, 1, 0)
        articles = []
        for group in at(panel, 4) or []:
            for node in group if isinstance(group, list) else []:
                if is_article(node):
                    articles.append(parse_article(node, edition))
        name = clean_text(at(head, 10))
        if not name and not articles:
            continue
        if isinstance(publication, str) and ids.publication_domain(publication):
            domain = ids.publication_domain(publication)
        elif isinstance(domain, str):   # sometimes "www.site.de/section"
            domain = _host("https://" + domain.split("://")[-1])
        else:
            domain = None
        out.append({
            "publisher": {
                "id": publication if isinstance(publication, str) else None,
                "name": name,
                "domain": domain,
                "google_link": topic_google_link(publication, edition) if isinstance(publication, str) else None,
                "logo": _logo(at(head, 9)),
                "banner": _logo(at(head, 0)),
                "wordmark": _logo(at(head, 1)),
            },
            "tagline": clean_text(at(head, 18)),
            "description": clean_text(at(head, 21)),
            "updated_at": iso_from_ts(at(head, 7, 0)),
            "articles": articles,
        })
    return out


# ---- RSS ------------------------------------------------------------------------------------------------

def _rss_date(text):
    if not text:
        return None
    try:
        return iso_from_ts(parsedate_to_datetime(text).timestamp())
    except (TypeError, ValueError):
        return None


def parse_rss(xml_text, edition=None):
    """A news.google.com RSS feed -> (feed title, [article]). RSS items carry
    no image, publisher id or publisher URL — those stay null (`link` is
    filled when the caller resolves it)."""
    raw = xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
    root = ElementTree.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return None, []
    items = []
    for item in channel.findall("item"):
        google = (item.findtext("link") or "").strip()
        article = rss_article_id(google) or (item.findtext("guid") or "").strip() or None
        title, source_from_title = _split_title(item.findtext("title"))
        source = item.find("source")
        source_name = clean_text(source.text) if source is not None and source.text else source_from_title
        homepage = _http(source.get("url")) if source is not None else None
        related = []
        for row in _related(item.findtext("description") or ""):
            if row.get("id") and row["id"] != article:
                related.append(blank_article(
                    id=row["id"], title=row.get("title"),
                    google_link=article_google_link(row["id"], edition),
                    publisher=blank_publisher(name=row.get("source"))))
        entry = blank_article(
            id=article, title=title or None, google_link=article_google_link(article, edition),
            published_at=_rss_date(item.findtext("pubDate")),
            publisher=blank_publisher(name=source_name, domain=_host(homepage), link=homepage))
        entry["story"] = None
        entry["related_articles"] = related
        items.append(entry)
    return clean_text(channel.findtext("title")), items


def blank_publisher(**fields):
    out = {"id": None, "name": None, "domain": None, "link": None, "google_link": None, "icon": None}
    out.update(fields)
    return out


def blank_article(**fields):
    """The article object with every key present (null / [] when unknown),
    for surfaces that carry less than the rpc node (RSS)."""
    out = {"id": None, "title": None, "link": None, "amp_link": None, "google_link": None, "snippet": None,
           "label": None, "kicker": None, "published_at": None, "image": None, "publisher": None, "authors": []}
    out.update(fields)
    return out
