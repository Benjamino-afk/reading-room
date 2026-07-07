"""Turn a feed entry into a stored article body — the product's core promise.

When a feed ships only a summary we follow the link-out, run a readability
extraction over the full page, and keep the complete text + images locally.
"""
import re

import httpx
import trafilatura
from bs4 import BeautifulSoup

from . import config, images, reddit

_SUMMARY_WORDS = 200   # below this, treat the entry as summary-only and fetch
_COMIC_WORDS = 40
_PHOTO_WORDS = 60


def _entry_html(entry) -> str:
    if entry.get("content"):
        return entry["content"][0].get("value", "")
    return entry.get("summary", "") or ""


def _plain(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _fetch(url: str) -> str | None:
    fetch_url, headers = reddit.prepare(url, {"User-Agent": config.USER_AGENT})
    try:
        r = httpx.get(
            fetch_url, timeout=config.FETCH_TIMEOUT, follow_redirects=True,
            headers=headers,
        )
        r.raise_for_status()
        return r.text
    except httpx.HTTPError:
        return None


def _paragraphs(html: str) -> list[str]:
    """Readable paragraphs via trafilatura, falling back to raw <p> tags."""
    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    if text:
        return [p.strip() for p in text.split("\n") if p.strip()]
    soup = BeautifulSoup(html or "", "html.parser")
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    paras = [p for p in paras if p]
    if paras:
        return paras
    fallback = _plain(html)
    return [fallback] if fallback else []


def _image_srcs(html: str) -> list[str]:
    """Main-content image srcs, preferring trafilatura's content detection."""
    xml = trafilatura.extract(
        html, include_images=True, include_comments=False, output_format="xml"
    )
    if xml:
        soup = BeautifulSoup(xml, "xml")
        srcs = [g.get("src") for g in soup.find_all("graphic") if g.get("src")]
        if srcs:
            return srcs
    soup = BeautifulSoup(html or "", "html.parser")
    return [img.get("src") for img in soup.find_all("img") if img.get("src")]


def _classify(words: int, n_images: int) -> tuple[str, int | None]:
    if words < _COMIC_WORDS and n_images >= 3:
        return "comic", n_images
    if words < _PHOTO_WORDS and n_images >= 1:
        return "photo", None
    return "text", None


def extract_entry(entry, full_text: bool) -> dict:
    link = entry.get("link")
    html = _entry_html(entry)
    base = link

    if full_text and link and _word_count(_plain(html)) < _SUMMARY_WORDS:
        fetched = _fetch(link)
        if fetched:
            html, base = fetched, link

    paragraphs = _paragraphs(html)
    img_urls = images.localize_many(_image_srcs(html), base) if base else []

    words = sum(_word_count(p) for p in paragraphs)
    snippet = paragraphs[0][:200] if paragraphs else ""
    type_, panels = _classify(words, len(img_urls))

    return {
        "type": type_, "panels": panels,
        "body_json": paragraphs, "image_paths": img_urls,
        "snippet": snippet, "words": words,
    }
