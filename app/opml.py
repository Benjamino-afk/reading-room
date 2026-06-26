"""OPML import / export."""
from xml.sax.saxutils import escape

from bs4 import BeautifulSoup

from . import db, feeds


def export() -> str:
    rows = "".join(
        f'    <outline text="{escape(f["name"])}" title="{escape(f["name"])}" '
        f'type="rss" xmlUrl="{escape(f["url"])}" '
        f'htmlUrl="{escape(f["siteUrl"] or "")}"/>\n'
        for f in db.list_feeds()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        "  <head><title>Reading Room feeds</title></head>\n"
        f"  <body>\n{rows}  </body>\n</opml>\n"
    )


def import_(xml: str) -> int:
    """Add every feed in an OPML document. Returns count added."""
    soup = BeautifulSoup(xml, "xml")
    existing = {f["url"] for f in db.list_feeds()}
    added = 0
    for outline in soup.find_all("outline"):
        url = outline.get("xmlUrl")
        if not url or url in existing:
            continue
        try:
            feeds.add(url, full_text=True)
            existing.add(url)
            added += 1
        except Exception as e:
            print(f"[opml] skip {url}: {e}", flush=True)
    return added
