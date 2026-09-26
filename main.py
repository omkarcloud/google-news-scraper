"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. The endpoint functions live in google_news/feeds.py
(headlines, topic, local, publisher and author feeds, home, showcase),
google_news/search.py, google_news/stories.py (full coverage),
google_news/articles.py (article links) and google_news/catalog.py (topics,
editions, autocomplete). `edition` is "<COUNTRY>:<language>", e.g. "US:en",
"GB:en", "IN:hi" (google_news/editions.py lists all 90).
"""
import json
import os

from google_news import feeds, refs, search, stories

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # the US top headlines: 20 stories per page, each with its related coverage
    headlines = feeds.top_headlines("US:en")
    save("top_headlines_us.json", headlines)

    # up to 100 articles for a keyword, with each publisher URL decoded
    save("search_openai.json", search.search("OpenAI", "US:en", time_published="past_week"))

    # full coverage of the first headline's story
    story = next((a["story"]["id"] for a in headlines["articles"] if a["story"]), None)
    if story:
        save("story.json", stories.story(refs.resolve_story(story), "US:en"))
