# Reading Room — self-hosted on :8087 (LIVE)

Self-hosted RSS/Atom reader whose point is full self-containment: it fetches the *complete* article (following link-outs past summary-only feeds) and stores body + images locally. One header switch flips between three layouts over the same data: Home (magazine), Office (mail client), Board (kanban).

## Architecture
Python 3.12 FastAPI + SQLite (single file, WAL) in one container; vanilla-JS SPA served by FastAPI, no build step. Extraction via trafilatura; APScheduler polls every `POLL_INTERVAL` min. It sits behind `reading-room-auth` (oauth2-proxy → Cognito pool `reading-room`).

## Commands
- Local: `DATA_DIR=./data uvicorn app.main:app --reload --port 8080`
- Tests/screenshots: Node + CDP harness in repo (see its README section)
- Deploy: push to GitHub → Actions builds `ghcr.io/benjamino-afk/reading-room:latest` → **user** re-pulls/redeploys in Portainer on the host (never deploy from here)

## Current focus
Stable. Last work (2026-11-08): Office + Board reworked to carry Reading Room's identity
(feed dots, Newsreader titles, real content) with every non-functional Outlook/Jira control
removed. Board columns derive from read state (`colOf`: read wins), cap at 50 per column,
and have live search. `titleOf`/`snippetOf` give untitled items a headline and drop
feed boilerplate (a paragraph repeated in 3+ of a feed's items; `bodyOf` never filters
a body to nothing). Dark-mode accent buttons use dark text for AA. Poller fix live since
2026-11-08. Next ideas: Home never shows images (every item is type "text"); the 500-item
API cap makes "All Stories" unread totals disagree with the list.

## Gotchas
- DB + images live in the `/data` volume (a host bind-mount on local disk, not NFS — so it is NOT covered by the NAS backup) — schema changes need a migration path, there's real data. `db._migrate()` adds columns in place on `init()`.
- Portainer paste gotcha: pasting multi-line env values into the stack editor mangles them.
- oauth2-proxy config holds the Cognito secret — Portainer env box, never compose.
- **Reddit:** anonymous `.rss` is IP-throttled to ~1 req/window; `app/reddit.py` paces requests to fit it. For ~100 req/min, set `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` (script app) in the stack env — OAuth then activates automatically, no code change. A failing feed shows a ⚠ badge in the feed manager.

- **Never add a job with `next_run_time=None`** — that is how APScheduler pauses a job, so it is created permanently paused and silently never fires (it cost this app its entire scheduled poll, from the initial commit to 2026-09-14). Assert on `next_run_time`, not on the absence of errors.
