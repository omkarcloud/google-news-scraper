"""The 15 Google News endpoints. Every path is served with and without the
`/google-news` prefix, so code generated against the hosted API (paths like
/top-headlines) runs unchanged against this server.

Params are validated by the same marshmallow schemas the hosted API uses
(google_news/schemas.py), so defaults, enums and error messages are
identical: unknown params are rejected, `country` + `language` must name a
real Google News edition, and ONE param per input (topic, publication,
location, author, story, article) accepts the plain value or a pasted
news.google.com link. List endpoints page with `page` and return count /
per_page / current_page / total_pages / next / previous first, exactly like
the hosted API.
"""
import json
from urllib.parse import urlencode

from bottle import request, response, route

from google_news import articles, catalog, feeds, schemas, search, stories
from schema_fields import load_query
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError

PREFIX = "/google-news"


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The request query as unicode strings (bottle 0.12's .get() hands back
    latin-1 decoded bytes, so a UTF-8 "São Paulo" would arrive garbled)."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def _page_link(params, page):
    if not page:
        return None
    query = {k: v for k, v in params.items() if v not in (None, "")}
    query["page"] = page
    return f"{request.urlparts.scheme}://{request.urlparts.netloc}{request.path}?{urlencode(query)}"


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate(result, params):
    """Lift the scraper's `pagination` block into the flat shape the hosted
    API returns: count / per_page / current_page / total_pages / next /
    previous first, then the data."""
    pagination = result.pop("pagination", None) or {}
    result.pop("count", None)
    page = _as_int(pagination.get("page")) or _as_int(params.get("page")) or 1
    total_pages = max(_as_int(pagination.get("total_pages")), 0)
    out = {
        "count": pagination.get("total_count"),
        "per_page": pagination.get("items_per_page"),
        "current_page": page,
        "total_pages": total_pages,
        "next": _page_link(params, page + 1 if page < total_pages else None),
        "previous": _page_link(params, page - 1 if page > 1 else None),
    }
    out.update(result)
    return out


def call(path, schema, impl, paginated=False):
    """Validate the query with the endpoint's schema, run it, and map every
    failure the way the hosted API does: bad params -> 400, missing topic /
    publisher / story / place -> 404, upstream failure or block -> 502,
    anything else -> 500."""
    params = query_dict()
    data, error = load_query(schema, params)
    if error:
        return json_response(error, 400)
    try:
        result = impl(**data)
    except ValueError as e:
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:
        return json_response({"error": f"google-news rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Blocked as e:
        return json_response({"error": f"google-news blocked the request, retry later: {e}"}, 502)
    except UpstreamError as e:
        return json_response({"error": f"google-news {path} failed: {e}"}, 502)
    except Exception as e:
        return json_response({"error": f"google-news {path} failed: {type(e).__name__}: {e}"}, 500)
    return json_response(paginate(result, params) if paginated else result)


P = True   # paginated (page)

# (public path, request schema, endpoint function, paginated) — the order of the docs.
ENDPOINTS = [
    ("/top-headlines", schemas.TopHeadlinesSchema, feeds.top_headlines, P),
    ("/autocomplete", schemas.AutocompleteSchema, catalog.autocomplete, False),
    ("/search", schemas.SearchSchema, search.search, P),
    ("/story", schemas.StorySchema, stories.story, False),
    ("/article/resolve", schemas.ArticleResolveSchema, articles.resolve, False),
    ("/topic/articles", schemas.TopicArticlesSchema, feeds.topic_articles, P),
    ("/topic/details", schemas.TopicDetailsSchema, catalog.topic_details, False),
    ("/local-headlines", schemas.LocalHeadlinesSchema, feeds.local_headlines, P),
    ("/publication/articles", schemas.PublicationArticlesSchema, feeds.publication_articles, P),
    ("/publication/details", schemas.PublicationDetailsSchema, catalog.publication_details, False),
    ("/author/articles", schemas.AuthorArticlesSchema, feeds.author_articles, P),
    ("/home", schemas.HomeSchema, feeds.home, False),
    ("/showcase", schemas.ShowcaseSchema, feeds.showcase, P),
    ("/topics", schemas.TopicsSchema, catalog.topics, False),
    ("/editions", schemas.EditionsSchema, catalog.editions, False),
]


def mount(path, schema, impl, paginated):
    """Serve one endpoint at /path and /google-news/path."""
    def handler():
        return call(path, schema, impl, paginated)
    handler.__name__ = "google_news_" + path.strip("/").replace("/", "_").replace("-", "_")
    route(path, method="GET")(handler)
    route(PREFIX + path, method="GET")(handler)


for _path, _schema, _impl, _paginated in ENDPOINTS:
    mount(_path, _schema, _impl, _paginated)


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": [p for p, *_ in ENDPOINTS]})
