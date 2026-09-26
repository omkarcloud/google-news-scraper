"""Record raw Google News replies into google_news/fixtures/*.json.gz for
the offline parser tests (test_parsers.py). Hits Google.

    python -m google_news.record_fixtures

Each fixture is {"kind": "rpc" | "text", "edition": ceid, "data": <decoded
rpc data | response text>} so the tests replay exactly what the parsers see.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_news import catalog, fetch, ids, parsers  # noqa: E402
from google_news.editions import edition  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def save(name, kind, ceid, data):
    os.makedirs(FIXTURES, exist_ok=True)
    with gzip.open(os.path.join(FIXTURES, f"{name}.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"kind": kind, "edition": ceid, "data": data}, f, ensure_ascii=False)
    print("saved", name)


def rpc(name, ed, rpcid, args):
    data = fetch.rpc(rpcid, args, hl=ed.hl, gl=ed.country, label=name)
    save(name, "rpc", ed.ceid, data)
    return data


def main():
    us, hi, de = edition("US:en"), edition("IN:hi"), edition("DE:de")
    headlines = ids.headlines_id(us)
    feed = rpc("headlines_us", us, "EAfJqe", ["gtsreq", us.context(), None, headlines, ""])
    rpc("headlines_info_us", us, "Qxytce", ["gtireq", us.context(), headlines])
    rpc("world_hi", hi, "EAfJqe", ["gtsreq", hi.context(), None, catalog.topic_id("WORLD", hi), ""])
    business = catalog.topic_id("BUSINESS", us)
    rpc("business_info_us", us, "Qxytce", ["gtireq", us.context(), business])
    rpc("nav_us", us, "BAeCvc", ["gnmreq", us.context()])
    rpc("nav_de", de, "BAeCvc", ["gnmreq", de.context()])
    rpc("home_us", us, "Giukpf", ["gbreq", us.context()])
    rpc("showcase_us", us, "l99YQ", ["ggctreq", us.context(), ""])
    cnn = ids.publication_id("cnn.com")
    rpc("publication_info_cnn", us, "Qxytce", ["gtireq", us.context(), cnn])
    rpc("publication_cnn", us, "EAfJqe", ["gtsreq", us.context(), None, cnn, ""])
    articles = parsers.parse_feed(feed, us)
    author = next((au["id"] for a in articles for au in a["authors"] if au["id"]), None)
    if author:
        rpc("author_info", us, "Qxytce", ["gtireq", us.context(), author])
    # the story with the most editorial groups among the first headlines
    best = None
    for a in articles[:10]:
        if not a["story"]:
            continue
        data = fetch.rpc("WuSwme", ["waareq", us.context()[0], a["story"]["id"]] + [None] * 9 + [0, 1],
                         hl=us.hl, gl=us.country)
        groups = sum(1 for c in (parsers.at(data, 2, 1, 3) or []) if isinstance(c, list) and c and c[0] == 2)
        if best is None or groups > best[0]:
            best = (groups, data)
    if best:
        save("story_us", "rpc", us.ceid, best[1])
    text = fetch.get_text(f"{fetch.SITE}/rss/search?q=tesla&hl=en-US&gl=US&ceid=US:en", label="search")
    save("search_tesla_us", "text", us.ceid, text)
    top = fetch.get_text(f"{fetch.SITE}/rss?hl=en-US&gl=US&ceid=US:en", label="rss top")
    save("rss_top_us", "text", us.ceid, top)


if __name__ == "__main__":
    main()
