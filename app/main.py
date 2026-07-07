"""Reading Room — FastAPI app: JSON API, image serving, and the SPA."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, feeds, opml, scheduler

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Reading Room", lifespan=lifespan)


class FeedIn(BaseModel):
    url: str
    fullText: bool = True


class ArticlePatch(BaseModel):
    read: bool | None = None
    status: str | None = None


# ---- articles --------------------------------------------------------------

@app.get("/api/articles")
def get_articles(feed: str = "all"):
    return db.list_articles(feed)


@app.patch("/api/articles/{article_id}")
def patch_article(article_id: int, patch: ArticlePatch):
    if patch.status is not None and patch.status not in ("todo", "doing", "done"):
        raise HTTPException(400, "invalid status")
    db.update_article(article_id, patch.read, patch.status)
    return {"ok": True}


@app.post("/api/articles/mark-all-read")
def mark_all(feed: str = "all"):
    db.mark_all_read(feed)
    return {"ok": True}


# ---- feeds -----------------------------------------------------------------

@app.get("/api/feeds")
def get_feeds():
    return db.list_feeds()


@app.post("/api/feeds")
def post_feed(body: FeedIn):
    try:
        feed_id = feeds.add(body.url, body.fullText)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": feed_id}


@app.delete("/api/feeds/{feed_id}")
def remove_feed(feed_id: int):
    db.delete_feed(feed_id)
    return {"ok": True}


@app.post("/api/feeds/{feed_id}/refresh")
def refresh_feed(feed_id: int):
    try:
        return {"new": feeds.poll(feed_id)}
    except Exception as e:  # a throttled/blocked source shouldn't 500 the UI
        return {"new": 0, "error": feeds.friendly_error(e)}


@app.post("/api/refresh")
def refresh_all():
    return {"new": feeds.poll_all()}


# ---- OPML ------------------------------------------------------------------

@app.get("/api/opml")
def opml_export():
    return Response(
        opml.export(), media_type="text/x-opml",
        headers={"Content-Disposition": "attachment; filename=reading-room.opml"},
    )


@app.post("/api/opml")
def opml_import(xml: str = Body(..., media_type="text/plain")):
    return {"added": opml.import_(xml)}


# ---- images + SPA ----------------------------------------------------------

@app.get("/img/{name}")
def get_image(name: str):
    path = (config.IMAGES_DIR / name).resolve()
    if config.IMAGES_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    idx = STATIC_DIR / "index.html"
    if idx.is_file():
        return FileResponse(idx)
    return PlainTextResponse("Reading Room backend running. Frontend not built yet.")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
