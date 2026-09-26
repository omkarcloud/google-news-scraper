"""Offline tests: ids, editions, input resolution, schemas, and every
endpoint function run over recorded upstream replies (google_news/fixtures/,
captured 2026-09-26 by record_fixtures.py). The transport is replaced by a
fake that serves the fixture matching each rpc / URL, so parse and shape
code runs for real.

    python -m pytest google_news/test_parsers.py -q
"""
import gzip
import json
import os
import sys
from io import BytesIO

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bottle  # noqa: E402
from google_news import (articles, catalog, editions, feeds, fetch, ids, parsers, refs, schemas,  # noqa: E402
                         search, stories)
from google_news.shared import page_slice  # noqa: E402
from schema_fields import load_query  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
US = editions.edition("US:en")
CNN = ids.publication_id("cnn.com")
WORLD_HI = "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtaHBHZ0pKVGlnQVAB"
BUSINESS_US = "CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx6TVdZU0JXVnVMVlZUR2dKVlV5Z0FQAQ"
SEATTLE = "CAAqIQgKIhtDQkFTRGdvSUwyMHZNR1E1YW5JU0FtVnVLQUFQAQ"


def fixture(name):
    with gzip.open(os.path.join(FIXTURES, name + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)["data"]


# ---- fake transport ---------------------------------------------------------------------------------------------

def _rpc_fixture(rpcid, args):
    topic = args[3] if rpcid == "EAfJqe" else (args[2] if rpcid == "Qxytce" else None)
    hl = args[1][0] if rpcid in ("EAfJqe", "Qxytce", "BAeCvc") else None
    if rpcid == "EAfJqe":
        if topic == CNN:
            return "publication_cnn"
        if topic == WORLD_HI:
            return "world_hi"
        if topic == ids.publication_id("notarealpublisher12345.com"):
            return None   # -> error code 5
        return "headlines_us"
    if rpcid == "Qxytce":
        if topic == CNN:
            return "publication_info_cnn"
        if topic == BUSINESS_US:
            return "business_info_us"
        if ids.describe(topic).get("mid", "").startswith("/g/"):
            return "author_info"
        return "headlines_info_us"
    if rpcid == "BAeCvc":
        return "nav_de" if hl == "de" else "nav_us"
    return {"Giukpf": "home_us", "l99YQ": "showcase_us", "WuSwme": "story_us"}.get(rpcid)


def fake_batch(calls, *, hl="en-US", gl="US", label=None, source_path="/"):
    out = []
    for rpcid, args in calls:
        if rpcid == "Fbv4je":
            out.append(fetch.RpcReply(rpcid, ["garturlres", f"https://publisher.example/{args[2][-6:]}", 1,
                                              f"https://publisher.example/amp/{args[2][-6:]}"], None))
            continue
        name = _rpc_fixture(rpcid, args)
        out.append(fetch.RpcReply(rpcid, fixture(name), None) if name else
                   fetch.RpcReply(rpcid, None, fetch.NOT_FOUND_CODE))
    return out


def fake_get_text(url, label, headers=None, timeout=None):
    if "/rss/search" in url:
        return fixture("search_tesla_us")
    if "/rss/articles/" in url:
        return '<div data-n-a-id="x" data-n-a-ts="1790233839" data-n-a-sg="AbIaSL_sig"></div>'
    if "suggestqueries" in url:
        return json.dumps(["tesl", ["tesla", "tesla stock"], ["", ""], [], {"google:suggestrelevance": [1250, 900]}])
    raise AssertionError(f"unexpected GET {url}")


def fake_redirect(url, label):
    if "/geo/" in url:
        return None if "xyzzy" in url else f"https://news.google.com/rss/topics/{SEATTLE}?hl=en-US"
    if "/topic/BUSINESS" in url:
        return f"https://news.google.com/rss/topics/{BUSINESS_US}?hl=en-US&gl=US&ceid=US:en"
    if "/topic/WORLD" in url and "gl=IN" in url:
        return f"https://news.google.com/rss/topics/{WORLD_HI}?hl=hi&gl=IN&ceid=IN:hi"
    return "https://news.google.com/rss/unsupported"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(fetch, "batch", fake_batch)
    monkeypatch.setattr(fetch, "get_text", fake_get_text)
    monkeypatch.setattr(fetch, "redirect_location", fake_redirect)
    monkeypatch.setattr("cache.storage", lambda: None, raising=False)
    fetch._memo.clear()
    yield
    fetch._memo.clear()


# ---- ids / editions / refs ---------------------------------------------------------------------------------------

def test_ids_round_trip():
    assert ids.publication_id("bbc.com") == "CAAqIAgKIhpDQklTRFFnTWFna0tCMkppWXk1amIyMG9BQVAB"
    assert ids.headlines_id(US) == "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pWVXlnQVAB"
    assert ids.describe(CNN) == {"kind": "publication", "domain": "cnn.com"}
    assert ids.describe("CAAqNggKIjBDQklTSGpvSmMzUnZjbmt0TXpZd1NoRUtEd2lrOHItREVoRTFYWGdaWDA5dnRTZ0FQAQ")["kind"] == "story"
    assert ids.describe("CAQqKggAKiYICiIgQ0JBU0Vnb0lMMjB2TURsdWJWOFNBbVZ1R2dKVlV5Z0FQAQ")["kind"] == "section"
    assert ids.describe("CAAq!!garbage")["kind"] is None
    assert ids.describe("CBMiabc")["kind"] == "article"


def test_editions():
    assert editions.resolve_edition() == "US:en"
    assert editions.resolve_edition("us", "es") == "US:es-419"
    assert editions.resolve_edition("uk") == "GB:en"
    assert editions.resolve_edition("BR", "pt") == "BR:pt-419"
    assert editions.resolve_edition("IL", "iw") == "IL:he"
    with pytest.raises(ValueError, match="hi"):
        editions.resolve_edition("IN", "kn")
    with pytest.raises(ValueError, match="no DK edition"):
        editions.resolve_edition("DK")
    rows = editions.list_editions("IN")
    assert rows[0]["is_default"] and rows[0]["edition"] == "IN:en" and len(rows) == 9
    assert US.context()[0][7] == "US:en" and editions.edition("IN:hi").hl == "hi"


def test_refs_one_param_forms():
    assert refs.resolve_topic("tech") == {"topic": "TECHNOLOGY", "section": None}
    link = f"https://news.google.com/topics/{BUSINESS_US}/sections/CAQiXENCQVNQd29JTDIwdk1EbHpNV1lTQW1WdUdnSlZVeUlQQ0FRYUN3b0pMMjB2TURsNU5IQnRLaG9LR0FvVVRVRlNTMFZVVTE5VFJVTlVTVTlPWDA1QlRVVWdBU2dBKioIAComCAoiIENCQVNFZ29JTDIwdk1EbHpNV1lTQW1WdUdnSlZVeWdBUAFQAQ?hl=en-US"
    resolved = refs.resolve_topic(link)
    assert resolved["topic"] == BUSINESS_US and resolved["section"].startswith("CAQ")
    with pytest.raises(ValueError, match="story"):
        refs.resolve_topic("CAAqNggKIjBDQklTSGpvSmMzUnZjbmt0TXpZd1NoRUtEd2lrOHItREVoRTFYWGdaWDA5dnRTZ0FQAQ")
    assert refs.resolve_publication("https://www.cnn.com/world") == CNN
    assert refs.resolve_publication("www.CNN.com") == CNN
    assert refs.resolve_publication(f"https://news.google.com/publications/{CNN}?hl=en-US") == CNN
    with pytest.raises(ValueError):
        refs.resolve_publication("not a domain")
    assert refs.resolve_location("  Paris,  France ") == "Paris, France"
    assert refs.resolve_location(f"https://news.google.com/topics/{SEATTLE}") == SEATTLE
    assert refs.resolve_article("https://news.google.com/rss/articles/CBMiabcdefghijklmnop?oc=5") == "CBMiabcdefghijklmnop"
    assert refs.resolve_article("https://news.google.com/read/CBMiabcdefghijklmnop?hl=en") == "CBMiabcdefghijklmnop"
    assert refs.resolve_source("https://www.reuters.com/world/") == "reuters.com"


def test_schemas():
    data, err = load_query(schemas.TopicArticlesSchema, {"topic": "world", "country": "in", "language": "hi"})
    assert err is None and data == {"topic": "WORLD", "section": None, "page": 1, "edition": "IN:hi"}
    data, err = load_query(schemas.SearchSchema, {"query": "tesla"})
    assert data["resolve_links"] is True and data["sort"] == "relevance" and data["edition"] == "US:en"
    _, err = load_query(schemas.SearchSchema, {"query": "x", "from_date": "2026-09-20", "to_date": "2026-09-01"})
    assert "from_date" in err["errors"]
    _, err = load_query(schemas.TopHeadlinesSchema, {"country": "IN", "language": "kn"})
    assert "language" in err["errors"]
    _, err = load_query(schemas.TopHeadlinesSchema, {"typo": "1"})
    assert err is not None
    data, _ = load_query(schemas.PublicationArticlesSchema, {"publication": "cnn.com", "section": "Recent"})
    assert data["publication"] == CNN and data["section"] == "recent"


def test_search_query_builder():
    assert search.build_query("elon musk", "past_month", "2026-09-01", None, "reuters.com", True) == \
        'intitle:"elon musk" when:30d after:2026-09-01 site:reuters.com'
    assert search.build_query("tesla") == "tesla"


def test_page_slice():
    items, block = page_slice(list(range(45)), 3)
    assert items == list(range(40, 45)) and block["total_pages"] == 3 and block["total_count"] == 45
    assert page_slice([], 1)[0] == []
    with pytest.raises(ValueError):
        page_slice(list(range(5)), 2)


# ---- parsers + endpoints over fixtures -------------------------------------------------------------------------

def _check_article(a):
    assert list(a)[:12] == ["id", "title", "link", "amp_link", "google_link", "snippet", "label", "kicker",
                            "published_at", "image", "publisher", "authors"]
    assert a["id"] and a["title"] and a["google_link"].startswith("https://news.google.com/read/")


def test_top_headlines():
    out = feeds.top_headlines("US:en")
    block = out["pagination"]
    assert block["total_count"] >= 30 and len(out["articles"]) == 20
    assert out["topic"]["name"] and out["topic"]["id"] == ids.headlines_id(US)
    for a in out["articles"]:
        _check_article(a)
        assert a["link"].startswith("http") and a["publisher"]["name"]
    assert any(a["story"] and a["story"]["title"] and a["related_articles"] for a in out["articles"])
    assert any(a["image"] and a["image"]["width"] for a in out["articles"])
    assert any(au["id"] for a in out["articles"] for au in a["authors"])
    ids_seen = [a["id"] for a in out["articles"]] + [r["id"] for a in out["articles"] for r in a["related_articles"]]
    assert len(ids_seen) == len(set(ids_seen))


def test_topic_articles_with_section_and_edition():
    out = feeds.topic_articles("BUSINESS", "US:en", section="markets")
    assert out["topic"]["key"] == "BUSINESS" and out["section"]["name"] == "Markets"
    with pytest.raises(ValueError, match="Markets"):
        feeds.topic_articles("BUSINESS", "US:en", section="nope")
    hi = feeds.topic_articles("WORLD", "IN:hi")
    assert hi["edition"] == {"country": "IN", "language": "hi", "edition": "IN:hi"} and hi["articles"]


def test_local_publication_author():
    local = feeds.local_headlines("Seattle", "US:en")
    assert local["location"]["name"] and local["articles"]   # (the fake serves the Headlines info)
    with pytest.raises(fetch.NewsNotFound):
        feeds.local_headlines("xyzzy", "US:en")
    pub = feeds.publication_articles(CNN, "US:en")
    assert pub["publication"]["name"] == "CNN" and pub["publication"]["domain"] == "cnn.com"
    assert all("cnn.com" in (a["publisher"]["domain"] or "") for a in pub["articles"])
    with pytest.raises(fetch.NewsNotFound):
        feeds.publication_articles(ids.publication_id("notarealpublisher12345.com"), "US:en")
    author_id = "CAAqKAgKIiJDQkFTRXdvTkwyY3ZNVEZtTW1Kb2Qyc3pOaElDWlc0b0FBUAE"
    author = feeds.author_articles(author_id, "US:en")
    assert author["author"]["name"] and set(author["author"]) == {"id", "name", "google_link", "image", "initials"}


def test_topics_and_details():
    us = catalog.topics("US:en")
    keys = [t["key"] for t in us["topics"]]
    assert keys[0] == "HEADLINES" and "WORLD" in keys and "BUSINESS" in keys and "LOCAL" not in keys
    de = catalog.topics("DE:de")
    assert de["edition"]["edition"] == "DE:de" and "SCIENCE" in [t["key"] for t in de["topics"]]
    details = catalog.topic_details("BUSINESS", "US:en")
    assert details["topic"]["key"] == "BUSINESS" and len(details["topic"]["sections"]) >= 5
    pub = catalog.publication_details(CNN, "US:en")
    assert pub["publication"]["sections"][0]["name"]


def test_home_showcase():
    home = feeds.home("US:en")
    assert home["title"] and home["sections"][0]["articles"]
    assert home["sections"][0]["more"]["id"].startswith("CAAq")
    show = feeds.showcase("US:en")
    panel = show["panels"][0]
    assert panel["publisher"]["name"] and panel["articles"] and "/" not in (panel["publisher"]["domain"] or "")
    assert show["pagination"]["items_per_page"] == 10


def test_story():
    out = stories.story("CAAqNggKIjBDQklTSGpvSmMzUnZjbmt0TXpZd1NoRUtEd2lrOHItREVoRTFYWGdaWDA5dnRTZ0FQAQ", "US:en")
    assert list(out)[:5] == ["id", "title", "google_link", "image", "article_count"]
    assert out["title"] and out["articles"] and out["article_count"] >= len(out["articles"])
    for a in out["top_articles"] + out["articles"]:
        _check_article(a)
    assert any(a["snippet"] for a in out["articles"])
    for post in out["x_posts"]:
        assert post["link"].startswith("https://x.com/") and post["author"]["username"]
    for section in out["sections"]:
        assert section["title"] and section["articles"]


def test_search_and_resolve():
    out = search.search("tesla", "US:en", sort="newest")
    assert out["google_query"] == "tesla" and len(out["articles"]) == 20
    dates = [a["published_at"] for a in out["articles"] if a["published_at"]]
    assert dates == sorted(dates, reverse=True)
    for a in out["articles"]:
        _check_article(a)
        assert a["link"].startswith("https://publisher.example/") and a["publisher"]["name"]
    raw = search.search("tesla", "US:en", resolve_links=False, page=2)
    assert all(a["link"] is None for a in raw["articles"]) and raw["pagination"]["page"] == 2
    one = articles.resolve("CBMiabcdefghijklmnop")
    assert one["link"] == "https://publisher.example/klmnop" and one["amp_link"].endswith("/amp/klmnop")


def test_rss_top_clusters():
    _title, items = parsers.parse_rss(fixture("rss_top_us"), US)
    assert items and any(i["related_articles"] for i in items)
    assert all(r["publisher"]["name"] for i in items for r in i["related_articles"])


def test_partial_payloads_never_crash():
    assert parsers.parse_feed(None) == [] and parsers.parse_feed([[], [None]]) == []
    assert parsers.parse_topic_info(["gtires", None]) is None
    assert parsers.parse_story([]) ["articles"] == []
    assert parsers.parse_showcase(["x"]) == [] and parsers.parse_home(None)["sections"] == []
    node = [13, [13, "CBMixyz"], "Title only", None, None, None, None]
    a = parsers.parse_article(node)
    assert a["title"] == "Title only" and a["image"] is None and a["publisher"] is None and a["authors"] == []


# ---- a mounted route (route_glue + schema + endpoint) ---------------------------------------------------------

def _call(app, path, query=""):
    env = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": query, "SERVER_NAME": "localhost",
           "SERVER_PORT": "80", "wsgi.input": BytesIO(b""), "wsgi.errors": sys.stderr, "wsgi.url_scheme": "http",
           "wsgi.version": (1, 0), "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False}
    status = {}
    body = b"".join(app(env, lambda s, h: status.update(status=s)))
    return int(status["status"][:3]), json.loads(body)


def test_routes_mounted(monkeypatch):
    route_glue = pytest.importorskip("route_glue")   # the grow service's route plumbing
    app = bottle.Bottle()
    monkeypatch.setattr(route_glue, "route", app.route)
    register = route_glue.route_table("google-news", public_host="google-news-scraper.omkar.cloud")
    register("/google-news/top-headlines", schemas.TopHeadlinesSchema, feeds.top_headlines, paginated=True)
    register("/google-news/publication/articles", schemas.PublicationArticlesSchema, feeds.publication_articles,
             paginated=True)
    status, body = _call(app, "/google-news/top-headlines", "country=US&page=2")
    assert status == 200 and body["current_page"] == 2 and body["previous"].endswith("page=1")
    assert body["next"].startswith("https://google-news-scraper.omkar.cloud/google-news/top-headlines?")
    status, body = _call(app, "/google-news/top-headlines", "country=IN&language=kn")
    assert status == 400 and "language" in body["errors"]
    status, body = _call(app, "/google-news/publication/articles", "publication=notarealpublisher12345.com")
    assert status == 404


# ---- transport escalation --------------------------------------------------------------------------------------

class _Resp:
    def __init__(self, status, text="", url="https://news.google.com/x", headers=None):
        self.status_code, self.text, self.url, self.headers = status, text, url, headers or {}


def test_escalation_ladder(monkeypatch):
    import config
    statuses = iter([429, 429, 429])
    used = []

    class FakeSession:
        def request(self, *a, **k):
            return _Resp(next(statuses), "unusual traffic")

        def close(self):
            pass

    monkeypatch.setattr(fetch, "_new_session", lambda proxy: used.append(proxy) or FakeSession())
    monkeypatch.setattr(config, "google_news_fallback_proxy", lambda: "http://fallback-exit")
    monkeypatch.setattr(config, "google_news_proxy", lambda: None)
    monkeypatch.setattr(config, "GOOGLE_NEWS_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(config, "RETRY_BACKOFF", 0)
    monkeypatch.setattr(fetch._browser, "fetch", lambda *a, **k: "from-browser")
    fetch._local.__dict__.clear()
    text, _url, _headers = fetch.request("GET", "https://news.google.com/rss", label="t", headers={})
    assert text == "from-browser"
    assert used[0] is None and used[1:] == ["http://fallback-exit", "http://fallback-exit"]
    fetch._local.__dict__.clear()


def test_not_found_and_bad_request_are_not_retried(monkeypatch):
    import config
    calls = []

    class FakeSession:
        def request(self, *a, **k):
            calls.append(1)
            return _Resp(404)

        def close(self):
            pass

    monkeypatch.setattr(fetch, "_new_session", lambda proxy: FakeSession())
    monkeypatch.setattr(config, "google_news_proxy", lambda: None)
    fetch._local.__dict__.clear()
    with pytest.raises(fetch.NewsNotFound):
        fetch.request("GET", "https://news.google.com/x", label="t", headers={})
    assert calls == [1]
    fetch._local.__dict__.clear()


def test_decode_batch_error_codes():
    body = ')]}\'\n\n123\n[["wrb.fr","EAfJqe",null,null,null,[5],"1"],["wrb.fr","Qxytce","[\\"gtires\\",null]",null,null,null,"2"]]\n'
    out = fetch.decode_batch(body)
    assert out["1"] == ("EAfJqe", None, 5) and out["2"][1] == ["gtires", None]
    with pytest.raises(fetch.NewsUpstreamError):
        fetch.decode_batch("<html>nope</html>")
