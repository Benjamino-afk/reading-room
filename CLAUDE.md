# Reading Room — ngihome :8087 (LIVE)

Self-hosted RSS/Atom reader whose point is full self-containment: it fetches the *complete* article (following link-outs past summary-only feeds) and stores body + images locally. One header switch flips between three layouts over the same data: Home (magazine), Office (mail client), Board (kanban).

## Architecture
Python 3.12 FastAPI + SQLite (single file, WAL) in one container; vanilla-JS SPA served by FastAPI, no build step. Extraction via trafilatura; APScheduler polls every `POLL_INTERVAL` min. It sits behind `reading-room-auth` (oauth2-proxy → Cognito pool `reading-room`, ap-southeast-2_S4dFr1uaQ).

## Commands
- Local: `DATA_DIR=./data uvicorn app.main:app --reload --port 8080`
- Tests/screenshots: Node + CDP harness in repo (see its README section)
- Deploy: push to GitHub → Actions builds `ghcr.io/benjamino-afk/reading-room:latest` → **user** re-pulls/redeploys in ngihome Portainer (never deploy from here)

## Current focus
Stable. Last work (2026-07-10): retention — a daily job prunes read articles older than
`PRUNE_DAYS` (default 30) and GCs images they solely referenced (`db.prune_read` +
`images.delete_local`, wired in `scheduler.py`); Office view reworked to an Outlook look
(centered email-card reading pane + a stronger boxed Delete/Archive ribbon group).
Deployed to the NAS 2026-07-11 (re-pull done; DB migrated on boot; first prune fires
24h after boot). Since that re-pull: stories auto-mark read on open, and a floating
pill shows live sync progress (`GET /api/progress`, polled while busy) — awaiting the
next re-pull.

## Gotchas
- DB + images live in the `/data` volume (`/volume1/tank/config/reading-room` on ngihome — LOCAL disk there, not NFS, so it is NOT in the NAS backup) — schema changes need a migration path, there's real data. `db._migrate()` adds columns in place on `init()`.
- Portainer paste gotcha: pasting multi-line env values into the stack editor mangles them (see memory project_reading_room).
- oauth2-proxy config holds the Cognito secret — Portainer env box, never compose.
- **Reddit:** anonymous `.rss` is IP-throttled to ~1 req/window; `app/reddit.py` paces requests to fit it. For ~100 req/min, set `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` (script app) in the stack env — OAuth then activates automatically, no code change. A failing feed shows a ⚠ badge in the feed manager.

- **Never add a job with `next_run_time=None`** — that is how APScheduler pauses a job, so it is created permanently paused and silently never fires (it cost this app its entire scheduled poll, from the initial commit to 2026-09-14). Assert on `next_run_time`, not on the absence of errors.
