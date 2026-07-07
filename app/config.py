"""Runtime config, read once from the environment."""
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "reading-room.sqlite"

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))      # minutes
READONLY = os.getenv("READONLY", "0") == "1"
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "12"))
FETCH_TIMEOUT = float(os.getenv("FETCH_TIMEOUT", "20"))

# Reddit wants a unique, descriptive UA; override via env to include your
# Reddit username if you hit throttling (e.g. "ReadingRoom/0.1 by u/you").
USER_AGENT = os.getenv(
    "USER_AGENT",
    "ReadingRoom/0.1 (+https://github.com/Benjamino-afk/reading-room)",
)

# App-only OAuth for Reddit feeds (optional — see app/reddit.py).
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")

# Per-feed identity colours, assigned round-robin as feeds are added.
FEED_COLORS = [
    "#b5532e", "#5f7a55", "#4f5b9a", "#9a6b3e", "#7d7468", "#a89e8d",
]


def ensure_dirs() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
