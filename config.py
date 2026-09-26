"""Configuration for the Google News Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT               port the API listens on (default 8000)
    GOOGLE_NEWS_PROXY  proxy URL, e.g. http://user:pass@host:port (default:
                       none — direct). Google News answered hundreds of calls
                       in a row from one home IP without a block in our tests,
                       so you very likely don't need this. When set, a
                       connection that Google blocks (403 / 429 / captcha)
                       retries through it for 15 minutes.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

GOOGLE_NEWS_PROXY = os.environ.get("GOOGLE_NEWS_PROXY") or None

GOOGLE_NEWS_DIRECT_COOLDOWN = 900       # seconds a blocked connection keeps using GOOGLE_NEWS_PROXY
GOOGLE_NEWS_MAX_ATTEMPTS = 3            # curl attempts per call before the browser fallback
GOOGLE_NEWS_BROWSER_FALLBACK = True     # replay a call in a headed Chrome when every curl attempt is blocked
GOOGLE_NEWS_BROWSER_IDLE_SECONDS = 300  # close that Chrome after this long unused
GOOGLE_NEWS_RESOLVE_WORKERS = 8         # parallel article-link decodes per /search page


def google_news_proxy():
    """Proxy for every request (None = direct, the default)."""
    return None


def google_news_fallback_proxy():
    """Proxy a blocked request (and the browser fallback) moves to."""
    return os.environ.get("GOOGLE_NEWS_PROXY") or None
