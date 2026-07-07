"""Reddit app-only OAuth.

Reddit rate-limits *unauthenticated* listing/feed requests to roughly one per
minute per IP (a 200 comes back with ``x-ratelimit-remaining: 0`` and a ~50s
``x-ratelimit-reset``), so a self-hosted reader on a single IP starves the
moment it polls more than one subreddit. An app-only OAuth token lifts the
ceiling to ~100 requests/minute and is served from ``oauth.reddit.com``.

Register a Reddit app (https://www.reddit.com/prefs/apps → "create app",
type **script**) and set ``REDDIT_CLIENT_ID`` / ``REDDIT_CLIENT_SECRET``. With
no credentials configured this module is a no-op: requests fall through to the
unauthenticated path (which still works, just slowly, with the backoff in
``feeds._fetch``).
"""
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from . import config

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_lock = threading.Lock()
_token: dict = {"value": None, "exp": 0.0}

# --- request pacing ---------------------------------------------------------
# Reddit rate-limits *anonymous* .rss to ~1 request/window per IP. Rather than
# let a burst of subreddit polls 429 all-but-the-first, we serialize Reddit
# traffic and space it by whatever reset Reddit last reported. Self-tuning: with
# OAuth (100/min) the remaining budget stays high, so pacing is a no-op.
_PACE_CAP = 65.0          # never hold off longer than this between requests
_pace_lock = threading.Lock()
_next_ok = 0.0            # monotonic time before which no new request may fire


def _is_reddit(host: str) -> bool:
    host = host.lower()
    return host == "reddit.com" or host.endswith(".reddit.com")


def is_reddit(url: str) -> bool:
    return _is_reddit(urlsplit(url).hostname or "")


def wait_turn() -> None:
    """Block the calling thread until the shared Reddit window allows a request.

    Only the background poller's thread blocks here, so a multi-minute pace over
    a poll cycle never touches the web server or the UI.
    """
    with _pace_lock:
        delay = _next_ok - time.monotonic()
    if delay > 0:
        time.sleep(min(delay, _PACE_CAP))


def note_response(r: httpx.Response) -> None:
    """Learn from a response's rate-limit headers when the next request may fire.
    When the window is spent, hold off until Reddit says it resets."""
    global _next_ok
    try:
        remaining = float(r.headers.get("x-ratelimit-remaining", "1"))
        reset = float(r.headers.get("x-ratelimit-reset", "0"))
    except ValueError:
        return
    with _pace_lock:
        if remaining < 1.0 and reset > 0:
            _next_ok = time.monotonic() + min(reset, _PACE_CAP)
        else:
            _next_ok = time.monotonic()  # budget available — no wait next time


def _get_token() -> str | None:
    """Return a cached app-only bearer token, fetching one if needed.

    Returns None when credentials are unconfigured or the token fetch fails —
    callers then use the unauthenticated URL unchanged.
    """
    if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET):
        return None
    with _lock:
        if _token["value"] and time.time() < _token["exp"]:
            return _token["value"]
        try:
            r = httpx.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET),
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.FETCH_TIMEOUT,
            )
            r.raise_for_status()
            tok = r.json()
        except (httpx.HTTPError, ValueError, KeyError) as e:
            print(f"[reddit] token fetch failed: {e}", flush=True)
            return None
        _token["value"] = tok.get("access_token")
        _token["exp"] = time.time() + float(tok.get("expires_in", 3600)) - 60
        return _token["value"]


def prepare(url: str, headers: dict) -> tuple[str, dict]:
    """If ``url`` points at reddit and OAuth is configured, rewrite it to
    ``oauth.reddit.com`` and attach a bearer token. Otherwise return unchanged.
    """
    parts = urlsplit(url)
    if not _is_reddit(parts.hostname or ""):
        return url, headers
    token = _get_token()
    if not token:
        return url, headers
    new_url = urlunsplit(parts._replace(netloc="oauth.reddit.com"))
    return new_url, {**headers, "Authorization": f"bearer {token}"}
