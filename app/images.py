"""Fetch article images and store them locally so nothing hotlinks out."""
import hashlib
import mimetypes
from urllib.parse import urljoin

import httpx

from . import config

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg", "image/avif": ".avif",
}


def localize(client: httpx.Client, src: str, base_url: str) -> str | None:
    """Download one image; return its local /img/<hash> url, or None on failure."""
    url = urljoin(base_url, src)
    if not url.lower().startswith(("http://", "https://")):
        return None
    try:
        r = client.get(url, timeout=config.FETCH_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except (httpx.HTTPError, ValueError):
        return None

    ctype = r.headers.get("content-type", "").split(";")[0].strip()
    if not ctype.startswith("image/"):
        return None
    ext = _EXT_BY_TYPE.get(ctype) or mimetypes.guess_extension(ctype) or ".img"

    digest = hashlib.sha1(r.content).hexdigest()[:20]
    name = f"{digest}{ext}"
    (config.IMAGES_DIR / name).write_bytes(r.content)
    return f"/img/{name}"


def delete_local(urls: list[str]) -> int:
    """Remove locally-stored images by their ``/img/<name>`` url. Returns the count
    actually removed; missing files are ignored."""
    removed = 0
    for u in urls:
        name = u.rsplit("/", 1)[-1]
        if not name or "/" in name or "\\" in name:
            continue
        try:
            (config.IMAGES_DIR / name).unlink()
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            pass
    return removed


def localize_many(srcs: list[str], base_url: str) -> list[str]:
    """Download up to MAX_IMAGES images, returning local urls (deduped)."""
    out: list[str] = []
    seen: set[str] = set()
    headers = {"User-Agent": config.USER_AGENT}
    with httpx.Client(headers=headers) as client:
        for src in srcs:
            if config.MAX_IMAGES and len(out) >= config.MAX_IMAGES:
                break
            if src in seen:
                continue
            seen.add(src)
            local = localize(client, src, base_url)
            if local:
                out.append(local)
    return out
