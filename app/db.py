"""SQLite access layer. One file, WAL mode, plain sqlite3 — no ORM needed."""
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    url        TEXT NOT NULL UNIQUE,        -- feed (xml/json) url
    site_url   TEXT,                        -- human site url
    color      TEXT NOT NULL,
    full_text  INTEGER NOT NULL DEFAULT 1,  -- follow link-outs + store full body
    capability TEXT NOT NULL DEFAULT 'summary',  -- fulltext|comics|images|summary
    added      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id     INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid        TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'text',     -- text|comic|photo
    title       TEXT NOT NULL,
    snippet     TEXT NOT NULL DEFAULT '',
    body_json   TEXT NOT NULL DEFAULT '[]',       -- list[str] paragraphs
    image_paths TEXT NOT NULL DEFAULT '[]',       -- list[str] local /img urls
    panels      INTEGER,                          -- comic panel count
    time        REAL NOT NULL,                    -- unix ts (published)
    words       INTEGER NOT NULL DEFAULT 0,
    read        INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'todo',     -- todo|doing|done
    UNIQUE (feed_id, guid)
);

CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id);
CREATE INDEX IF NOT EXISTS idx_articles_time ON articles(time DESC);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    config.ensure_dirs()
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns to existing DBs in place (there's real data on the NAS)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(feeds)")}
    if "last_error" not in cols:
        conn.execute("ALTER TABLE feeds ADD COLUMN last_error TEXT")
    if "last_fetched" not in cols:
        conn.execute("ALTER TABLE feeds ADD COLUMN last_fetched REAL")


# ---- feeds -----------------------------------------------------------------

def list_feeds() -> list[dict]:
    with connect() as conn:
        feeds = conn.execute("SELECT * FROM feeds ORDER BY added").fetchall()
        rows = []
        for f in feeds:
            unread = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE feed_id=? AND read=0",
                (f["id"],),
            ).fetchone()[0]
            rows.append({
                "id": f["id"], "name": f["name"], "url": f["url"],
                "siteUrl": f["site_url"], "color": f["color"],
                "fullText": bool(f["full_text"]), "capability": f["capability"],
                "unread": unread, "lastError": f["last_error"],
            })
        return rows


def next_color() -> str:
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    return config.FEED_COLORS[n % len(config.FEED_COLORS)]


def add_feed(name: str, url: str, site_url: Optional[str], full_text: bool) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO feeds (name, url, site_url, color, full_text, added) "
            "VALUES (?,?,?,?,?,?)",
            (name, url, site_url, next_color(), int(full_text), time.time()),
        )
        return cur.lastrowid


def delete_feed(feed_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM feeds WHERE id=?", (feed_id,))


def set_capability(feed_id: int, capability: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE feeds SET capability=? WHERE id=?", (capability, feed_id))


def set_feed_status(feed_id: int, error: Optional[str]) -> None:
    """Record the last fetch outcome — ``error`` is None on success."""
    with connect() as conn:
        conn.execute(
            "UPDATE feeds SET last_error=?, last_fetched=? WHERE id=?",
            (error, time.time(), feed_id),
        )


def get_feed(feed_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()


# ---- articles --------------------------------------------------------------

def article_exists(feed_id: int, guid: str) -> bool:
    with connect() as conn:
        return conn.execute(
            "SELECT 1 FROM articles WHERE feed_id=? AND guid=?", (feed_id, guid)
        ).fetchone() is not None


def insert_article(a: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO articles "
            "(feed_id, guid, type, title, snippet, body_json, image_paths, panels, time, words) "
            "VALUES (:feed_id,:guid,:type,:title,:snippet,:body_json,:image_paths,:panels,:time,:words)",
            a,
        )


def list_articles(feed: str = "all") -> list[dict]:
    sql = (
        "SELECT a.*, f.name AS feed_name, f.color AS feed_color "
        "FROM articles a JOIN feeds f ON f.id=a.feed_id "
    )
    params: tuple = ()
    if feed != "all":
        sql += "WHERE a.feed_id=? "
        params = (int(feed),)
    sql += "ORDER BY a.time DESC LIMIT 500"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_article_to_api(r) for r in rows]


def update_article(article_id: int, read: Optional[bool], status: Optional[str]) -> None:
    sets, params = [], []
    if read is not None:
        sets.append("read=?")
        params.append(int(read))
    if status is not None:
        sets.append("status=?")
        params.append(status)
        # keep board column and read-state in sync
        sets.append("read=?")
        params.append(1 if status == "done" else 0)
    if not sets:
        return
    params.append(article_id)
    with connect() as conn:
        conn.execute(f"UPDATE articles SET {','.join(sets)} WHERE id=?", params)


def prune_read(days: int) -> tuple[int, list[str]]:
    """Delete read articles older than ``days`` and return the number removed plus
    any local image urls left unreferenced by surviving articles, so the caller can
    reclaim those files. ``days <= 0`` disables pruning (returns 0, []).
    """
    if days <= 0:
        return 0, []
    cutoff = time.time() - days * 86400
    with connect() as conn:
        stale = conn.execute(
            "SELECT image_paths FROM articles WHERE read=1 AND time < ?", (cutoff,)
        ).fetchall()
        imgs: set[str] = set()
        for r in stale:
            imgs.update(json.loads(r["image_paths"]))
        deleted = conn.execute(
            "DELETE FROM articles WHERE read=1 AND time < ?", (cutoff,)
        ).rowcount
        # An image is content-addressed, so a surviving article may still cite one
        # a pruned article used — only delete files nothing references anymore.
        orphans = [
            u for u in imgs
            if conn.execute(
                "SELECT 1 FROM articles WHERE image_paths LIKE ? LIMIT 1", (f"%{u}%",)
            ).fetchone() is None
        ]
    return deleted, orphans


def mark_all_read(feed: str = "all") -> None:
    sql = "UPDATE articles SET read=1, status=CASE status WHEN 'done' THEN 'done' ELSE status END "
    params: tuple = ()
    if feed != "all":
        sql += "WHERE feed_id=?"
        params = (int(feed),)
    with connect() as conn:
        conn.execute(sql, params)


def _article_to_api(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "feedId": r["feed_id"],
        "feed": r["feed_name"],
        "feedColor": r["feed_color"],
        "type": r["type"],
        "panels": r["panels"],
        "title": r["title"],
        "snippet": r["snippet"],
        "body": json.loads(r["body_json"]),
        "images": json.loads(r["image_paths"]),
        "time": r["time"],
        "words": r["words"],
        "read": bool(r["read"]),
        "status": r["status"],
    }
