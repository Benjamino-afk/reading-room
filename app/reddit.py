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


def _is_reddit(host: str) -> bool:
    host = host.lower()
    return host == "reddit.com" or host.endswith(".reddit.com")


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
