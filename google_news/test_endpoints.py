"""Live smoke tests for every /google-news/* route (hits Google).

    python run.py &   # or the grow service: ONLY_SCRAPER=google-news SCRAPERS_PORT=7441 python run.py
    GOOGLE_NEWS_BASE=http://localhost:7441 python -m pytest google_news/test_endpoints.py -q

Checks shapes, the one-param-per-input link forms, the edition validation
and the 400 / 404 paths. Values are live, so assertions stay structural.
"""
import os

import pytest
import requests

BASE = os.environ.get("GOOGLE_NEWS_BASE", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="set GOOGLE_NEWS_BASE to run the live endpoint tests")
ARTICLE_KEYS = ["id", "title", "link", "amp_link", "google_link", "snippet", "label", "kicker", "published_at",
                "image", "publisher", "authors"]
PUBLISHER_KEYS = ["id", "name", "domain", "link", "google_link", "icon"]
PAGE_KEYS = ["count", "per_page", "current_page", "total_pages", "next", "previous"]


def get(path, status=200, **params):
    r = requests.get(f"{BASE}/google-news/{path}", params=params, timeout=120)
    assert r.status_code == status, (path, params, r.status_code, r.text[:500])
    return r.json()


def check_article(a, rich=True):
    assert list(a)[:len(ARTICLE_KEYS)] == ARTICLE_KEYS, list(a)
    assert a["id"] and a["title"] and a["google_link"].startswith("https://news.google.com/read/")
    assert a["published_at"] is None or a["published_at"].endswith("Z")
    assert list(a["publisher"]) == PUBLISHER_KEYS
    if rich:
        assert a["link"].startswith("http")
        assert a["publisher"]["name"]


def check_feed(data, head_key):
    assert list(data)[:len(PAGE_KEYS)] == PAGE_KEYS
    assert data[head_key]["id"].startswith("CAAq")
    assert data["articles"], "empty feed"
    for a in data["articles"]:
        check_article(a)
        assert "story" in a and "related_articles" in a
        for r in a["related_articles"]:
            check_article(r)
    assert data["edition"]["edition"]


@pytest.fixture(scope="module")
def headlines():
    return get("top-headlines")


def test_top_headlines(headlines):
    check_feed(headlines, "topic")
    assert headlines["count"] >= 30
    assert any(a["story"] and a["related_articles"] for a in headlines["articles"])
    assert headlines["next"] and "page=2" in headlines["next"]


def test_top_headlines_page_2_and_past_end():
    data = get("top-headlines", page=2)
    assert data["current_page"] == 2 and data["previous"]
    get("top-headlines", status=400, page=10)


def test_editions_validation():
    assert get("top-headlines", country="IN", language="hi")["edition"]["edition"] == "IN:hi"
    assert get("top-headlines", country="us", language="es")["edition"]["edition"] == "US:es-419"
    err = get("top-headlines", status=400, country="IN", language="kn")
    assert "hi" in err["error"]
    get("top-headlines", status=400, country="DK")
    get("top-headlines", status=400, bogus="1")


def test_topic_articles_forms():
    by_name = get("topic/articles", topic="business", section="markets")
    check_feed(by_name, "topic")
    assert by_name["topic"]["key"] == "BUSINESS" and by_name["section"]["name"] == "Markets"
    link = by_name["section"]["google_link"]
    by_link = get("topic/articles", topic=link)
    assert by_link["section"]["id"] == by_name["section"]["id"]
    by_id = get("topic/articles", topic=by_name["topic"]["id"])
    assert by_id["topic"]["id"] == by_name["topic"]["id"]
    err = get("topic/articles", status=400, topic="business", section="nonexistent tab")
    assert "Markets" in err["error"]
    get("topic/articles", status=400, topic="not-a-topic")


def test_topic_details_and_topics():
    data = get("topic/details", topic="SPORTS")
    assert data["topic"]["key"] == "SPORTS" and len(data["topic"]["sections"]) > 3
    topics = get("topics", country="DE")
    assert topics["topics"][0]["key"] == "HEADLINES" and topics["edition"]["edition"] == "DE:de"


def test_local_headlines():
    data = get("local-headlines", location="Seattle")
    check_feed(data, "location")
    assert data["location"]["name"] == "Seattle"
    get("local-headlines", status=404, location="xyzzyqqplace")


def test_publication(headlines):
    by_domain = get("publication/articles", publication="bbc.com")
    check_feed(by_domain, "publication")
    assert by_domain["publication"]["domain"] == "bbc.com"
    by_link = get("publication/articles", publication=by_domain["publication"]["google_link"])
    assert by_link["publication"]["id"] == by_domain["publication"]["id"]
    by_site = get("publication/details", publication="https://www.reuters.com/world/")
    assert by_site["publication"]["domain"] == "reuters.com" and by_site["publication"]["name"]
    get("publication/articles", status=404, publication="notarealpublisher12345.com")


def test_author(headlines):
    author = next((au for a in headlines["articles"] for au in a["authors"] if au["id"]), None)
    if author is None:
        pytest.skip("no author id on the headlines right now")
    data = get("author/articles", author=author["id"])
    check_feed(data, "author")
    assert get("author/articles", author=author["google_link"])["author"]["id"] == author["id"]


def test_story(headlines):
    story = next(a["story"] for a in headlines["articles"] if a["story"])
    data = get("story", story=story["id"])
    assert data["id"] == story["id"] and data["title"]
    assert data["article_count"] >= 5
    for a in data["articles"] + data["top_articles"]:
        check_article(a)
    assert get("story", story=story["google_link"])["id"] == story["id"]
    get("story", status=400, story="CBMiabc123456789012345")


def test_search():
    data = get("search", query="tesla", time_published="past_week", sort="newest")
    assert data["google_query"] == "tesla when:7d"
    assert data["articles"]
    for a in data["articles"]:
        check_article(a, rich=False)
    assert sum(1 for a in data["articles"] if a["link"]) >= len(data["articles"]) // 2
    dates = [a["published_at"] for a in data["articles"] if a["published_at"]]
    assert dates == sorted(dates, reverse=True)
    fast = get("search", query="openai", source="https://www.reuters.com", resolve_links="false")
    assert "site:reuters.com" in fast["google_query"] and all(a["link"] is None for a in fast["articles"])
    get("search", status=400, query="x", from_date="2026-09-20", to_date="2026-09-01")


def test_article_resolve(headlines):
    article = headlines["articles"][0]
    data = get("article/resolve", article=article["google_link"])
    assert data["id"] == article["id"] and data["link"].startswith("http")


def test_home_showcase_autocomplete():
    home = get("home")
    assert home["sections"] and home["sections"][0]["articles"]
    showcase = get("showcase")
    assert showcase["panels"] and showcase["panels"][0]["publisher"]["name"]
    sug = get("autocomplete", query="tesl")
    assert sug["suggestions"] and sug["suggestions"][0]["query"].startswith("tesl")
    assert get("editions")["count"] >= 80
