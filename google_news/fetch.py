"""Google News transport: plain curl_cffi with Chrome TLS, a headful
patchright in-page fetch as the last resort. Validated 2026-09-26.

Upstreams (all open: no cookie, no token, never rate limited in testing)
---------
  POST news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=<id,…>
       f.req=[[["<rpc>","<json args>",null,"<tag>"],…]]
         Qxytce  gtireq  [ctx, <topic | publication id>]           topic info + section tabs
         EAfJqe  gtsreq  [ctx, <section id|null>, <topic id>, ""]  the articles of a topic /
                                                                   section / publication / place / author
         BAeCvc  gnmreq  [ctx]                                     the edition's nav menu (topics)
         Giukpf  gbreq   [ctx]                                     the home page ("Your briefing")
         WuSwme  waareq  [ctx[0], <story id>, null×9, 0, 1]        a story's full coverage
         l99YQ   ggctreq [ctx, ""]                                 News Showcase panels
         Fbv4je  garturlreq                                        article id -> publisher URL
       A failed rpc answers ["wrb.fr", <rpc>, null, …, [<code>], …] (5 = not found).
  GET  news.google.com/rss[/search|/headlines/section/topic/<T>|/headlines/section/geo/<P>]
       (search, and the 302s that name a topic / place id)
  GET  news.google.com/rss/articles/<id>   the signature Fbv4je needs
  GET  suggestqueries.google.com/complete/search?client=chrome&ds=n

The HTML /search page is a hard /sorry captcha for every client (curl,
headful Chrome, residential exits) — search runs on the RSS feed.

Escalation per call (config.GOOGLE_NEWS_*): the thread's curl session (direct)
-> after a block the thread moves to a fallback exit for a while -> after
GOOGLE_NEWS_MAX_ATTEMPTS blocked attempts, one headful patchright Chrome
parked on news.google.com replays the call as an in-page fetch.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  NewsUpstreamError  transport failure / 5xx / unparseable body  -> 502
  NewsBlocked        403 / 429 / captcha                         -> 502
  NewsBadRequest     Google rejected the parameters (HTTP 400)   -> 400
  NewsNotFound       unknown topic / publication / story / place -> 404
"""
import json
import os
import sys
import threading
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from google_search.fetch import run_parallel, strip_xssi  # noqa: E402,F401 (re-exported)
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError  # noqa: E402

SITE = "https://news.google.com"
BATCH_PATH = "/_/DotsSplashUi/data/batchexecute"
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
IMPERSONATE = "chrome"
TIMEOUT = 30
PAGE_TIMEOUT = 45
NOT_FOUND_CODE = 5

# Consent cookies: an EU exit is otherwise bounced to consent.google.com on
# every HTML page (the RSS and batchexecute surfaces never are). Harmless
# elsewhere.
CONSENT_COOKIES = {
    "CONSENT": "YES+cb.20240101-01-p0.en+FX+999",
    "SOCS": "CAESHAgBEhJnd3NfMjAyNDAxMDEtMF9SQzIaAmVuIAEaBgiA_LyaBg",
}

PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
}
BATCH_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "origin": SITE,
    "referer": SITE + "/",
    "x-same-domain": "1",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}
SUGGEST_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": SITE + "/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}


class NewsUpstreamError(UpstreamError):
    """Transport failure, 5xx or an unparseable body — retryable."""


class NewsBlocked(NewsUpstreamError, Blocked):
    """403 / 429 / captcha — retryable on a fresh exit."""


class NewsBadRequest(BadRequest):
    """Google rejected the parameters — never retried."""


class NewsNotFound(NotFound):
    """Unknown topic / publication / story / place — never retried."""


def dump_debug(name, text):
    """Write a raw body to $GOOGLE_NEWS_DEBUG_DIR/<name>.txt."""
    dbg = os.environ.get("GOOGLE_NEWS_DEBUG_DIR", "")
    if dbg and text:
        try:
            os.makedirs(dbg, exist_ok=True)
            with open(os.path.join(dbg, name + ".txt"), "w") as f:
                f.write(text if isinstance(text, str) else repr(text))
        except OSError:
            pass


# ---- curl sessions -------------------------------------------------------------------------------------
# One curl session per worker thread (a curl handle must not be shared across
# threads). After a block the thread moves to the fallback exit for
# GOOGLE_NEWS_DIRECT_COOLDOWN seconds.
_local = threading.local()


def _new_session(proxy):
    from curl_cffi import requests as curl_requests
    sess = curl_requests.Session(impersonate=IMPERSONATE)
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
    for name, value in CONSENT_COOKIES.items():
        sess.cookies.set(name, value, domain=".google.com")
    return sess


def _session():
    via_fallback = getattr(_local, "fallback_until", 0) > time.time()
    entry = getattr(_local, "entry", None)
    if entry is not None and entry["fallback"] != via_fallback:
        _drop_session()
        entry = None
    if entry is None:
        proxy = config.google_news_proxy() or (config.google_news_fallback_proxy() if via_fallback else None)
        entry = _local.entry = {"session": _new_session(proxy), "fallback": via_fallback}
    return entry["session"]


def _drop_session():
    entry = getattr(_local, "entry", None)
    _local.entry = None
    if entry is not None:
        try:
            entry["session"].close()
        except Exception:
            pass


def _on_blocked():
    """The current exit was refused: move this thread to the fallback exit
    (a fresh sticky one each time) for a while."""
    if config.google_news_fallback_proxy() is not None:
        _local.fallback_until = time.time() + config.GOOGLE_NEWS_DIRECT_COOLDOWN
    _drop_session()


# ---- classification ------------------------------------------------------------------------------------

def _is_sorry(status, url, text):
    return "/sorry/" in (url or "") or (status in (200, 429) and "unusual traffic" in (text or "")[:8000])


def _classify(status, url, text, label, redirects_ok=False):
    """Raise the failure a response represents, or return its text."""
    if status in (403, 429) or _is_sorry(status, url, text):
        dump_debug(f"blocked_{label}", text)
        raise NewsBlocked(f"HTTP {status} on {label}")
    if "consent.google.com" in (url or ""):
        raise NewsBlocked(f"{label}: bounced to the consent page")
    if status == 400:
        raise NewsBadRequest(f"{label}: Google News rejected the request")
    if status == 404:
        raise NewsNotFound(f"{label}: not found")
    if redirects_ok and status in (301, 302, 303, 307, 308):
        return text
    if status != 200:
        raise NewsUpstreamError(f"HTTP {status} on {label}")
    return text


# ---- browser fallback ----------------------------------------------------------------------------------

class _Browser:
    """One headful patchright Chrome parked on news.google.com (fallback
    exit), opened on demand, reused while busy and closed after
    GOOGLE_NEWS_BROWSER_IDLE_SECONDS. Calls run as in-page fetches, so they
    carry the page's own cookies and TLS."""

    HOME = f"{SITE}/home?hl=en-US&gl=US&ceid=US:en"

    def __init__(self):
        self.lock = threading.Lock()
        self.driver = None
        self.last_used = 0.0
        self.closer = None

    def _open(self):
        from chrome_manager import create_scope
        from patchright_driver import PatchrightDriver
        with create_scope():
            driver = PatchrightDriver(proxy_url=config.google_news_fallback_proxy(), headless=False)
        try:
            driver.nav(self.HOME, mode="blocked", challenge_markers=("unusual traffic",))
        except Exception:
            driver.close()
            raise
        return driver

    def _drop(self):
        if self.driver is not None:
            try:
                self.driver.close()
            except Exception:
                pass
        self.driver = None

    def _close_when_idle(self):
        while True:
            time.sleep(30)
            with self.lock:
                if self.driver is None or time.time() - self.last_used > config.GOOGLE_NEWS_BROWSER_IDLE_SECONDS:
                    self._drop()
                    self.closer = None
                    return

    def fetch(self, method, url, headers, body, label):
        from patchright_driver import _FETCH_JS, FETCH_TIMEOUT_MS
        headers = {k: v for k, v in (headers or {}).items()
                   if not k.startswith(("sec-", "origin", "referer", "accept-language", "upgrade-"))}
        with self.lock:
            if self.driver is None:
                self.driver = self._open()
            if self.closer is None:
                self.closer = threading.Thread(target=self._close_when_idle, daemon=True)
                self.closer.start()
            self.last_used = time.time()
            try:
                res = self.driver.call(lambda page: page.evaluate(_FETCH_JS, {
                    "url": url, "method": method, "headers": headers, "body": body,
                    "referrer": self.HOME, "timeoutMs": FETCH_TIMEOUT_MS}))
            except Exception:
                self._drop()
                raise
            status = int((res or {}).get("status") or 0)
            if status in (403, 429):
                self._drop()   # the next fallback call starts on a fresh exit
        if not res or (not status and res.get("error")):
            raise NewsUpstreamError(f"browser fetch failed on {label}: {(res or {}).get('error')}")
        return _classify(status, res.get("url") or "", res.get("body") or "", label)


_browser = _Browser()


# ---- requests with the escalation ladder ---------------------------------------------------------------

def request(method, url, *, label, headers, timeout=TIMEOUT, body=None, browser=True, redirects=True):
    """One call -> (text, final url, response headers). Every block moves the
    thread to a fresh exit; after GOOGLE_NEWS_MAX_ATTEMPTS blocked attempts
    the headful browser replays it (when `browser`). With redirects=False a
    3xx is returned as-is (the caller reads its Location)."""
    attempts = max(1, int(config.GOOGLE_NEWS_MAX_ATTEMPTS))
    last, blocked_only = None, True
    for attempt in range(1, attempts + 1):
        sess = _session()
        try:
            resp = sess.request(method, url, headers=headers, data=body, timeout=timeout,
                                allow_redirects=redirects)
        except Exception as e:
            last, blocked_only = NewsUpstreamError(f"{label}: request failed: {type(e).__name__}: {e}"), False
            _drop_session()
        else:
            final = str(resp.url or url)
            try:
                text = _classify(resp.status_code, final, resp.text or "", label, redirects_ok=not redirects)
                return text, final, dict(resp.headers or {})
            except (NewsBadRequest, NewsNotFound):
                raise
            except NewsBlocked as e:
                last = e
                _on_blocked()
            except NewsUpstreamError as e:
                last, blocked_only = e, False
                _drop_session()
        if attempt < attempts:
            time.sleep(min(config.RETRY_BACKOFF * attempt * 0.5, 3))
    if browser and blocked_only and redirects and config.GOOGLE_NEWS_BROWSER_FALLBACK:
        print(f"google-news: every curl attempt on {label} was blocked; replaying it in a browser")
        return _browser.fetch(method, url, headers, body, label), url, {}
    raise last


def get_text(url, label, headers=None, timeout=PAGE_TIMEOUT):
    return request("GET", url, label=label, headers=headers or PAGE_HEADERS, timeout=timeout)[0]


def redirect_location(url, label):
    """GET without following redirects -> the Location header (None when
    the answer is not a redirect)."""
    _text, _final, headers = request("GET", url, label=label, headers=PAGE_HEADERS, redirects=False,
                                     browser=False)
    for key, value in headers.items():
        if key.lower() == "location":
            return value
    return None


# ---- batchexecute --------------------------------------------------------------------------------------

def decode_batch(text, label="batchexecute"):
    """A batchexecute body -> {tag: (rpcid, data | None, error code | None)}.
    Handles the plain `)]}'` JSON form and the `rt=c` chunked form."""
    body = strip_xssi(text)
    chunks = []
    try:
        chunks.append(json.loads(body))
    except ValueError:
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("[["):
                try:
                    chunks.append(json.loads(line))
                except ValueError:
                    continue
    out = {}
    for chunk in chunks:
        for item in chunk if isinstance(chunk, list) else []:
            if not (isinstance(item, list) and len(item) >= 3 and item[0] == "wrb.fr"):
                continue
            rpcid, payload = item[1], item[2]
            tag = str(item[6]) if len(item) > 6 and item[6] is not None else "generic"
            code = item[5][0] if len(item) > 5 and isinstance(item[5], list) and item[5] else None
            data = None
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                except ValueError:
                    dump_debug(f"badjson_{label}_{rpcid}", payload)
                    code = code or "unparseable"
            out[tag] = (rpcid, data, code)
    if not out:
        dump_debug(f"nodata_{label}", text)
        raise NewsUpstreamError(f"{label}: no rpc payload in the response")
    return out


class RpcReply:
    """One rpc's answer: `data` (None when it failed) and the error `code`."""
    __slots__ = ("rpcid", "data", "code")

    def __init__(self, rpcid, data, code):
        self.rpcid, self.data, self.code = rpcid, data, code

    @property
    def not_found(self):
        return self.code == NOT_FOUND_CODE


def batch(calls, *, hl="en-US", gl="US", label=None, source_path="/"):
    """Run several rpcs in ONE POST: [(rpcid, args), …] -> [RpcReply, …]
    aligned with `calls`."""
    if not calls:
        return []
    label = label or "+".join(dict.fromkeys(c[0] for c in calls))
    f_req = [[rpcid, json.dumps(args, separators=(",", ":"), ensure_ascii=False), None, str(i + 1)]
             for i, (rpcid, args) in enumerate(calls)]
    params = {"rpcids": ",".join(dict.fromkeys(c[0] for c in calls)), "source-path": source_path,
              "hl": hl, "gl": gl, "rt": "c"}
    body = urlencode({"f.req": json.dumps([f_req], separators=(",", ":"), ensure_ascii=False)})
    text = request("POST", f"{SITE}{BATCH_PATH}?{urlencode(params)}", label=label, headers=BATCH_HEADERS,
                   timeout=PAGE_TIMEOUT, body=body)[0]
    replies = decode_batch(text, label)
    out = []
    for i, (rpcid, _args) in enumerate(calls):
        reply = replies.get(str(i + 1))
        if reply is None and len(calls) == 1:
            reply = next(iter(replies.values()))
        if reply is None:
            out.append(RpcReply(rpcid, None, "missing"))
        else:
            out.append(RpcReply(reply[0], reply[1] if reply[2] is None else None, reply[2]))
    return out


def rpc(rpcid, args, *, hl="en-US", gl="US", label=None, not_found=None):
    """One rpc -> its data. A not-found code raises NewsNotFound(not_found);
    any other failure NewsUpstreamError."""
    reply = batch([(rpcid, args)], hl=hl, gl=gl, label=label)[0]
    if reply.data is None:
        if reply.not_found and not_found:
            raise NewsNotFound(not_found)
        raise NewsUpstreamError(f"{label or rpcid}: Google News answered error {reply.code}")
    return reply.data


# ---- memo + shared cache --------------------------------------------------------------------------------
# A feed (the ~70 stories of a topic, the 100 hits of a search) is fetched
# once and paged in memory: the in-process memo serves the next pages, the
# response cache (cache.py) shares it across pods.
_memo = {}
_memo_lock = threading.Lock()
MEMO_MAX = 256


def memoized(key, fn, ttl):
    now = time.monotonic()
    with _memo_lock:
        hit = _memo.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _memo_lock:
        _memo[key] = (now, value)
        if len(_memo) > MEMO_MAX:
            for old in sorted(_memo, key=lambda k: _memo[k][0])[:len(_memo) - MEMO_MAX]:
                _memo.pop(old, None)
    return value


def dataset(name, params, build, ttl):
    """A whole feed / reference dataset: in-process memo, then the response
    cache (shared across pods), then build()."""
    from cache import cached_call
    seconds = ttl.total_seconds() if hasattr(ttl, "total_seconds") else float(ttl)
    key = (name, json.dumps(params, sort_keys=True))
    return memoized(key, lambda: cached_call(f"google-news.dataset.{name}", params, lambda **_: build(), ttl),
                    ttl=min(seconds, 600))
