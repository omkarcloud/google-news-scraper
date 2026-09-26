"""Helpers shared by the /google-news/* endpoint modules: in-memory paging
(route_glue lifts the `pagination` block into the flat gateway shape)."""
import copy

from google_search.shared import pagination

PER_PAGE = 20


def page_slice(items, page, per_page=PER_PAGE):
    """One page of an in-memory list (deep-copied: feeds are shared memo
    objects) -> (items, pagination block). Page 1 of an empty list is fine;
    a page past the end is a 400."""
    total = len(items)
    total_pages = (total + per_page - 1) // per_page if per_page else 0
    if page > max(total_pages, 1):
        raise ValueError(f"page {page} is past the last page ({total_pages}).")
    start = (page - 1) * per_page
    return copy.deepcopy(items[start:start + per_page]), pagination(page, per_page, total)
