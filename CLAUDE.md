# Reading Room — NAS :8087 (LIVE)

Self-hosted RSS/Atom reader whose point is full self-containment: it fetches the *complete* article (following link-outs past summary-only feeds) and stores body + images locally. One header switch flips between three layouts over the same data: Home (magazine), Office (mail client), Board (kanban).

## Architecture
Python 3.12 FastAPI + SQLite (single file, WAL) in one container; vanilla-JS SPA served by FastAPI, no build step. Extraction via trafilatura; APScheduler polls every `POLL_INTERVAL` min. On the NAS it sits behind `reading-room-auth` (oauth2-proxy → Cognito pool `reading-room`, ap-southeast-2_S4dFr1uaQ).

## Commands
- Local: `DATA_DIR=./data uvicorn app.main:app --reload --port 8080`
- Tests/screenshots: Node + CDP harness in repo (see its README section)
- Deploy: push to GitHub → Actions builds `ghcr.io/benjamino-afk/reading-room:latest` → **user** re-pulls/redeploys on the NAS (never deploy from here)

## Current focus
Stable. No open feature thread.

## Gotchas
- DB + images live in the `/data` volume (`/volume1/tank/config/reading-room` on the NAS) — schema changes need a migration path, there's real data.
- Portainer paste gotcha: pasting multi-line env values into the stack editor mangles them (see memory project_reading_room).
- oauth2-proxy config holds the Cognito secret — Portainer env box, never compose.
