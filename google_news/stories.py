"""Story full coverage — the WuSwme rpc (waareq) behind
news.google.com/stories/<id> (validated 2026-09-26).

A story id is the `story.id` of any feed article (or the id in a /stories/
link). The reply's "Overview" tab holds, in page order: the section index,
optional titled groups ("Top news", "Posts on X", "Interviews", …), then the
"All coverage" list (~40-110 articles, newest first). Stories without
editorial groups carry only the list.
"""
from google_news import cache_config as ttl
from google_news import fetch, parsers
from google_news.editions import edition as get_edition


def story(story, edition):
    """Full coverage of one story."""
    ed = get_edition(edition)

    def build():
        # EXACTLY 9 nulls before (0, 1): with 8 the reply drops the editorial
        # groups (Top news, Posts on X, For context, …) and keeps only the list.
        args = ["waareq", ed.context()[0], story] + [None] * 9 + [0, 1]
        data = fetch.rpc("WuSwme", args, hl=ed.hl, gl=ed.country, label="story",
                         not_found=f"Google News has no story {story!r}.")
        parsed = parsers.parse_story(data, ed)
        if not parsed["id"] and not parsed["articles"] and not parsed["top_articles"]:
            raise fetch.NewsNotFound(f"Google News has no story {story!r}.")
        return parsed

    data = fetch.dataset("story", {"story": story, "edition": ed.ceid}, build, ttl.STORY_CACHE)
    sections = data.get("sections") or []
    return {
        "id": data.get("id") or story,
        "title": data.get("title"),
        "google_link": data.get("google_link"),
        "image": data.get("image"),
        "article_count": len(data.get("top_articles") or []) + len(data.get("articles") or []) + sum(
            len(s.get("articles") or []) for s in sections),
        "x_post_count": len(data.get("x_posts") or []),
        "top_articles": data.get("top_articles") or [],
        "x_posts": data.get("x_posts") or [],
        "sections": sections,
        "articles": data.get("articles") or [],
        "edition": ed.summary(),
    }
