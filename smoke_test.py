"""Quick end-to-end smoke test against a real feed. Run: python smoke_test.py"""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="rr-smoke-")
os.environ["POLL_INTERVAL"] = "999"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

FEED = "https://hnrss.org/frontpage"

with TestClient(app) as c:
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/api/feeds").json() == []

    r = c.post("/api/feeds", json={"url": FEED, "fullText": False})
    print("add feed:", r.status_code, r.json())
    assert r.status_code == 200, r.text

    feeds = c.get("/api/feeds").json()
    print("feeds:", [(f["name"], f["unread"], f["capability"]) for f in feeds])
    assert len(feeds) == 1 and feeds[0]["unread"] > 0
    fid = feeds[0]["id"]

    arts = c.get("/api/articles").json()
    print(f"articles: {len(arts)}; sample title:", arts[0]["title"][:60])
    a0 = arts[0]
    for k in ("id", "feedId", "feed", "feedColor", "type", "title",
              "snippet", "body", "images", "time", "words", "read", "status"):
        assert k in a0, f"missing key {k}"

    # read-state toggle
    c.patch(f"/api/articles/{a0['id']}", json={"read": True})
    assert c.get("/api/articles").json()[0]["read"] is True

    # board status <-> read sync
    c.patch(f"/api/articles/{a0['id']}", json={"status": "todo"})
    a = next(x for x in c.get("/api/articles").json() if x["id"] == a0["id"])
    assert a["status"] == "todo" and a["read"] is False

    # filter by feed
    assert len(c.get(f"/api/articles?feed={fid}").json()) == len(arts)

    # OPML round-trip
    opml = c.get("/api/opml").text
    assert "xmlUrl" in opml and FEED in opml
    print("opml export OK")

    # mark all read
    c.post("/api/articles/mark-all-read")
    assert all(x["read"] for x in c.get("/api/articles").json())

    # delete feed cascades
    c.delete(f"/api/feeds/{fid}")
    assert c.get("/api/feeds").json() == []
    assert c.get("/api/articles").json() == []

print("\nALL SMOKE TESTS PASSED")
