# Reading Room

A self-hosted RSS/Atom/JSON-feed reader whose defining feature is **full
self-containment**: the server fetches the *complete* article for every item —
following link-outs when a feed only ships a summary — and stores the body text
and images locally, so the reader never bounces you to another site.

One header switch flips the whole reading experience between three layouts over
the same data: **Home** (cozy paper magazine), **Office** (Outlook-style mail
client), **Board** (Jira-style To Read / Reading / Read kanban).

> Built from the `design_handoff_reading_room/` spec. That folder is design
> reference only and is never shipped.

## Stack
- **Backend:** Python 3.12 / FastAPI, SQLite (one file, WAL).
- **Extraction:** `trafilatura` readability + local image storage (no hotlinks).
- **Polling:** APScheduler, every `POLL_INTERVAL` minutes.
- **Frontend:** vanilla-JS SPA served by FastAPI (single container, no build step).

## Run locally
```bash
python -m venv .venv && . .venv/Scripts/activate   # or bin/activate on *nix
pip install -r requirements.txt
DATA_DIR=./data uvicorn app.main:app --reload --port 8080
# open http://localhost:8080
```

## Run with Docker
```bash
cp .env.example .env
docker compose up -d --build
# http://localhost:8087  (host 8087 -> container 8080)
```
SQLite DB + fetched images live in the `./data` volume.

## Config (`.env`)
| var | default | meaning |
|---|---|---|
| `DATA_DIR` | `/data` | DB + image storage |
| `POLL_INTERVAL` | `30` | minutes between automatic polls |
| `READONLY` | `0` | `1` disables all writes |
| `MAX_IMAGES` | `12` | images stored per article (0 = unlimited) |
| `FETCH_TIMEOUT` | `20` | seconds per feed/article fetch |

## API
| method | path | purpose |
|---|---|---|
| GET | `/api/articles?feed=<id\|all>` | list articles |
| PATCH | `/api/articles/{id}` | `{read?, status?}` (status⇄read kept in sync) |
| POST | `/api/articles/mark-all-read?feed=` | mark filtered set read |
| GET | `/api/feeds` | list feeds + unread counts |
| POST | `/api/feeds` | `{url, fullText}` — discovers feed from any site URL |
| DELETE | `/api/feeds/{id}` | remove feed (articles cascade) |
| POST | `/api/feeds/{id}/refresh`, `/api/refresh` | poll now |
| GET / POST | `/api/opml` | export / import OPML |
| GET | `/img/{name}` | locally stored article image |

## Tests
```bash
python smoke_test.py   # end-to-end against a live feed
```
