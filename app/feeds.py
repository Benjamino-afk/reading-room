"""Feed discovery, adding, and polling."""
import json
import time
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from . import config, db, extract, reddit

_MAX_BACKOFF = 30.0   # cap the single 429 retry wait (Reddit resets in ~50s)

_FEED_TYPES = (
    "application/rss+xml", "application/atom+xml", "application/feed+json",
    "application/json",
)


def _hash_guid(entry) -> str:
    return entry.get("id") or entry.get("link") or entry.get("title", "")


def _entry_time(entry) -> float:
    for key in ("published_parsed", "updated_parsed"):
        if entry.get(key):
            return time.mktime(entry[key])
    return time.time()


def _retry_wait(r: httpx.Response) -> float:
    """Seconds to wait before a single 429 retry, from whichever hint Reddit
    gives (``Retry-After`` or ``x-ratelimit-reset``), capped so a scheduled
    poll never stalls for long."""
    hint = r.headers.get("Retry-After") or r.headers.get("x-ratelimit-reset") or ""
    try:
        wait = float(hint) if hint else 3.0
    except ValueError:
        wait = 3.0
    return min(max(wait, 0.0), _MAX_BACKOFF)


def _fetch(url: str) -> httpx.Response:
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5",
    }
    url, headers = reddit.prepare(url, headers)  # OAuth-lift Reddit if configured
    is_rd = reddit.is_reddit(url)
    if is_rd:
        reddit.wait_turn()  # pace within Reddit's per-IP window
    r = httpx.get(url, timeout=config.FETCH_TIMEOUT, follow_redirects=True, headers=headers)
    if is_rd:
        reddit.note_response(r)
    if r.status_code == 429:  # rate-limited (Reddit et al.) — back off once, then give up
        wait = _retry_wait(r)
        if wait:
            time.sleep(wait)
            r = httpx.get(url, timeout=config.FETCH_TIMEOUT, follow_redirects=True, headers=headers)
            if is_rd:
                reddit.note_response(r)
    r.raise_for_status()
    return r


def discover(url: str):
    """Resolve any site/feed URL to a real feed URL + its human site URL.

    Returns (feed_url, site_url, parsed) where ``parsed`` is the already-fetched
    feed when the URL was itself a feed (else None). Raises ValueError if nothing
    parses. Returning the parse lets callers avoid re-fetching the same URL —
    which is what trips rate limits (e.g. Reddit 429s a burst of requests).
    """
    try:
        r = _fetch(url)
    except httpx.HTTPError as e:
        raise ValueError(f"could not fetch {url}: {e}") from e

    # Is the URL itself a feed?
    parsed = feedparser.parse(r.content)
    if parsed.entries:
        site = parsed.feed.get("link") or url
        return url, site, parsed

    # Otherwise it's a web page — look for <link rel=alternate> feed links.
    soup = BeautifulSoup(r.text, "html.parser")
    for link in soup.find_all("link", rel="alternate"):
        if link.get("type") in _FEED_TYPES and link.get("href"):
            feed_url = httpx.URL(str(r.url)).join(link["href"])
            return str(feed_url), url, None
    raise ValueError(f"no feed found at {url}")


def add(url: str, full_text: bool) -> int:
    feed_url, site_url, parsed = discover(url)
    if parsed is None:  # discovered a feed link on a web page — fetch it once
        parsed = feedparser.parse(_fetch(feed_url).content)
    name = parsed.feed.get("title") or urlparse(feed_url).netloc or feed_url
    feed_id = db.add_feed(name, feed_url, site_url, full_text)
    poll(feed_id, parsed)  # reuse the parse — no extra request
    return feed_id


def friendly_error(e: Exception) -> str:
    """A short, user-facing reason a feed failed to fetch."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 429:
            return "Rate-limited by the source (will retry next poll)."
        if code in (401, 403):
            return f"Blocked by the source (HTTP {code}) — may need authentication."
        return f"Source returned HTTP {code}."
    if isinstance(e, httpx.HTTPError):
        return "Could not reach the source."
    return str(e)


def poll(feed_id: int, parsed=None) -> int:
    """Fetch a feed and store any new articles. Returns count of new items.

    ``parsed`` may be a feed already fetched by the caller, to avoid a re-fetch.
    Records the fetch outcome on the feed (cleared on success) so the UI can
    show which feeds are failing.
    """
    if config.READONLY:
        return 0
    feed = db.get_feed(feed_id)
    if feed is None:
        return 0
    try:
        return _poll(feed, parsed)
    except Exception as e:
        db.set_feed_status(feed_id, friendly_error(e))
        raise


def _poll(feed, parsed=None) -> int:
    feed_id = feed["id"]
    if parsed is None:
        parsed = feedparser.parse(_fetch(feed["url"]).content)
    full_text = bool(feed["full_text"])
    new = 0
    caps: set[str] = set()
    for entry in parsed.entries:
        guid = _hash_guid(entry)
        if not guid or db.article_exists(feed_id, guid):
            continue
        ex = extract.extract_entry(entry, full_text)
        if ex["words"] >= 200:
            caps.add("fulltext")
        if ex["image_paths"]:
            caps.add("images")
        if ex["type"] == "comic":
            caps.add("comics")
        db.insert_article({
            "feed_id": feed_id,
            "guid": guid,
            "type": ex["type"],
            "title": entry.get("title", "(untitled)"),
            "snippet": ex["snippet"],
            "body_json": json.dumps(ex["body_json"]),
            "image_paths": json.dumps(ex["image_paths"]),
            "panels": ex["panels"],
            "time": _entry_time(entry),
            "words": ex["words"],
        })
        new += 1
    _record_capability(feed_id, caps)
    db.set_feed_status(feed_id, None)  # fetch succeeded — clear any prior error
    return new


def poll_all() -> int:
    total = 0
    for f in db.list_feeds():
        try:
            total += poll(f["id"])
        except Exception as e:  # one bad feed shouldn't stop the rest
            print(f"[poll] feed {f['id']} failed: {e}", flush=True)
    return total


def _record_capability(feed_id: int, caps: set[str]) -> None:
    for cap in ("fulltext", "comics", "images"):
        if cap in caps:
            db.set_capability(feed_id, cap)
            return
    db.set_capability(feed_id, "summary")
