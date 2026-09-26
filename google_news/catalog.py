"""Reference endpoints and the topic / place id plumbing every feed uses.

  editions        the (country, language) pairs Google News serves
  topics          an edition's topic menu (Headlines + the nav menu)
  topic details   a topic's / publication's name, image and section tabs
  autocomplete    Google's news query suggestions

Topic names resolve per edition (ids embed the language, and editions differ:
Germany merges Science & Technology): HEADLINES is built from its Knowledge
Graph mid, the others follow news.google.com/rss/headlines/section/topic/<KEY>,
whose 302 names the edition's topic id. Place names follow
/rss/headlines/section/geo/<place> the same way (Google geocodes the name; an
unknown place answers /rss/unsupported).
"""
import json
from urllib.parse import quote, urlencode

from google_news import cache_config as ttl
from google_news import fetch, ids, parsers
from google_news.editions import edition as get_edition
from google_news.editions import list_editions
from google_news.refs import TOPIC_NAMES

SITE = fetch.SITE


def editions(country=None):
    rows = list_editions(country)
    return {"count": len(rows), "editions": rows}


# ---- ids -----------------------------------------------------------------------------------------------------

def _topic_from_location(location):
    """/rss/topics/<id>?… -> <id>; /rss/unsupported -> None."""
    if not location or "/rss/topics/" not in location:
        return None
    return location.split("/rss/topics/", 1)[1].split("?")[0].split("/")[0] or None


def topic_id(topic, ed):
    """A topic KEY (WORLD, …) or an id -> the id in this edition."""
    if topic not in TOPIC_NAMES:
        return topic
    if topic == "HEADLINES":
        return ids.headlines_id(ed)

    def build():
        location = fetch.redirect_location(
            f"{SITE}/rss/headlines/section/topic/{topic}?{urlencode(ed.query())}", label=f"topic {topic}")
        found = _topic_from_location(location)
        if not found:
            raise fetch.NewsNotFound(f"The {ed.ceid} edition of Google News has no {topic} topic.")
        return found

    return fetch.dataset("topic_id", {"topic": topic, "edition": ed.ceid}, build, ttl.ID_CACHE)


def place_id(place, ed):
    """A place name -> the place topic id Google geocodes it to."""
    if place.startswith("CAAq"):
        return place

    def build():
        location = fetch.redirect_location(
            f"{SITE}/rss/headlines/section/geo/{quote(place, safe='')}?{urlencode(ed.query())}", label="place")
        found = _topic_from_location(location)
        if not found:
            raise fetch.NewsNotFound(f"Google News has no local news for {place!r}.")
        return found

    return fetch.dataset("place_id", {"place": place.lower(), "edition": ed.ceid}, build, ttl.ID_CACHE)


def topic_info(topic, ed):
    """gtireq for a topic / publication / place / author id (cached)."""
    def build():
        data = fetch.rpc("Qxytce", ["gtireq", ed.context(), topic], hl=ed.hl, gl=ed.country, label="topic info",
                         not_found="Google News has no such topic.")
        info = parsers.parse_topic_info(data, ed)
        if info is None:
            raise fetch.NewsNotFound("Google News has no such topic.")
        return info

    return fetch.dataset("topic_info", {"topic": topic, "edition": ed.ceid}, build, ttl.TOPIC_CACHE)


def match_section(info, section):
    """A section id or tab name -> the tab ({id, name, google_link}); raises
    ValueError with the topic's tab names when nothing matches."""
    if not section:
        return None
    tabs = info.get("sections") or []
    if section.startswith("CAQ"):
        for tab in tabs:
            if tab["id"] == section:
                return tab
        return {"id": section, "name": None, "google_link": parsers.topic_google_link(info["id"], None, section)}
    wanted = section.strip().lower()
    for tab in tabs:
        if (tab.get("name") or "").lower() == wanted:
            return tab
    for tab in tabs:
        if wanted in (tab.get("name") or "").lower():
            return tab
    names = ", ".join(t["name"] for t in tabs if t.get("name")) or "none"
    raise ValueError(f"{info.get('name') or 'This topic'} has no {section!r} section. Its sections: {names}.")


# ---- endpoints -----------------------------------------------------------------------------------------------

def topics(edition):
    """Headlines + the edition's nav-menu topics, with the stable key
    (WORLD, BUSINESS, …) when the topic is one of the standard ones."""
    ed = get_edition(edition)
    headlines = ids.headlines_id(ed)
    nav, info = fetch.batch([("BAeCvc", ["gnmreq", ed.context()]),
                             ("Qxytce", ["gtireq", ed.context(), headlines])],
                            hl=ed.hl, gl=ed.country, label="topics")
    if nav.data is None:
        raise fetch.NewsUpstreamError(f"topics: Google News answered error {nav.code}")
    head = parsers.parse_topic_info(info.data, ed) if info.data is not None else None
    rows = [{"id": headlines, "key": "HEADLINES", "name": (head or {}).get("name") or "Headlines",
             "google_link": parsers.topic_google_link(headlines, ed)}]
    rows += [row for row in parsers.parse_nav(nav.data, ed) if row["key"] != "LOCAL"]
    return {"count": len(rows), "topics": rows, "edition": ed.summary()}


def topic_details(topic, edition, section=None):
    """Name, type, image and section tabs of a topic, publication, place or
    author."""
    ed = get_edition(edition)
    info = json.loads(json.dumps(topic_info(topic_id(topic, ed), ed)))
    if topic in TOPIC_NAMES:
        info["key"] = topic
    out = {"topic": info}
    if section:
        out["section"] = match_section(info, section)
    out["edition"] = ed.summary()
    return out


def publication_details(publication, edition):
    """Name, domain, icon and tabs (Recent, News Showcase, …) of a publisher
    — `publication` may be a bare domain, so this doubles as the domain ->
    publication id lookup."""
    ed = get_edition(edition)
    info = json.loads(json.dumps(topic_info(publication, ed)))
    return {"publication": {"id": info["id"], "name": info.get("name"), "domain": info.get("domain"),
                            "google_link": info.get("google_link"), "icon": info.get("image"),
                            "sections": info.get("sections") or []},
            "edition": ed.summary()}


def autocomplete(query, edition):
    """Google's news query suggestions, best first."""
    ed = get_edition(edition)
    params = {"client": "chrome", "ds": "n", "q": query, "hl": ed.hl, "gl": ed.country.lower()}
    text = fetch.get_text(f"{fetch.SUGGEST_URL}?{urlencode(params)}", label="autocomplete",
                          headers=fetch.SUGGEST_HEADERS, timeout=fetch.TIMEOUT)
    try:
        data = json.loads(text)
    except ValueError:
        fetch.dump_debug("autocomplete", text)
        raise fetch.NewsUpstreamError("autocomplete: could not parse the suggestions")
    terms = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
    extra = data[4] if isinstance(data, list) and len(data) > 4 and isinstance(data[4], dict) else {}
    relevance = extra.get("google:suggestrelevance") or []
    suggestions = []
    for i, term in enumerate(terms):
        if isinstance(term, str) and term.strip():
            suggestions.append({"query": term, "relevance": relevance[i] if i < len(relevance) else None})
    return {"query": query, "count": len(suggestions), "suggestions": suggestions, "edition": ed.summary()}
