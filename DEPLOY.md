# Deploying Reading Room to the 204 NAS (Portainer / Docker)

Single container, builds on the NAS, default bridge network, host port **8087**.
You run the deploy; this file is the runbook.

## Target
- **Host:** Asustor AS5404T — `admin@192.168.1.204` (**must use `ssh -tt`**, ADM closes the channel without a PTY).
- **Path:** `/volume1/tank/config/reading-room/` (matches the `/volume1/tank/config/<app>` convention).
- **Data volume:** `./data` (SQLite DB + fetched images) — created on first run, owned by root-in-container. No PUID/PGID needed (the app runs as root inside its own container; nothing else touches the volume).
- **Network:** `network_mode: bridge` — required, since on ADM only the default bridge has internet egress. Single container, no peer DNS, so the legacy bridge is fine.

## 1. Confirm port 8087 is free on the 204
Known ports in use: Glance 8085, photo-scroller 8086, trade 8090, blur-review 8099, focal 8420.
8087 should be free — verify:
```bash
ssh -tt admin@192.168.1.204 "ss -tlnp 2>/dev/null | grep ':8087 ' || echo 'free'"
```
If taken, change the left side of `ports: 8087:8080` in docker-compose.yml.

## 2. Copy the project up
From the project folder on your machine (excludes the local venv / data):
```bash
cd "C:/Users/User/Documents/AIwork/RSS Server/reading-room"
scp -r app Dockerfile docker-compose.yml requirements.txt README.md \
    admin@192.168.1.204:/volume1/tank/config/reading-room/
```
(If `/volume1/tank/config/reading-room/` doesn't exist:
`ssh -tt admin@192.168.1.204 "mkdir -p /volume1/tank/config/reading-room"`.)

## 3. Build & start (on the NAS)
```bash
ssh -tt admin@192.168.1.204 \
  "cd /volume1/tank/config/reading-room && docker compose up -d --build"
```
First build pulls `python:3.12-slim` and compiles trafilatura/lxml — a few minutes on the N5105.

### Or via Portainer + GHCR (no NAS build — `admin` has no daemon build access)
Portainer can't build from a `build:` context, and the NAS `admin` account can't
reach the Docker daemon to build. So let CI build the image and have Portainer pull it:

1. `.github/workflows/docker-image.yml` builds on every push to `main` and publishes
   `ghcr.io/benjamino-afk/reading-room:latest`.
2. If the GHCR package is **private**, in Portainer add the registry once:
   Registries → Add → Custom → URL `ghcr.io`, username = your GitHub user,
   password = a PAT with `read:packages`. (Or make the package public on GitHub.)
3. Portainer → Stacks → Add stack → name `reading-room` → paste
   **`docker-compose.portainer.yml`** → Deploy. It pulls the prebuilt image; the
   data volume is the absolute path `/volume1/tank/config/reading-room/data`.
4. To update later: re-run the workflow (push to `main`), then in Portainer
   pull & redeploy the stack.

## 4. Verify
```bash
ssh -tt admin@192.168.1.204 "curl -fs http://localhost:8087/api/health"   # {"ok":true}
```
Then open over Tailscale: **http://as5404t-6005-1:8087** (or `http://192.168.1.204:8087` on the LAN).
Add a feed in the manager (e.g. `https://hnrss.org/frontpage`) and confirm articles + full-text fetch.

## 5. Glance tile
Add to the Glance config (Home Server → Media stack monitor), mirroring the blur-review/focal tiles:
```yaml
- title: Reading Room
  url: http://192.168.1.204:8087
  check-url: http://192.168.1.204:8087/api/health
  icon: si:rss
```
Then check the Glance dashboard renders it (per the NAS→Glance sync habit).

## Updating later
```bash
scp -r app admin@192.168.1.204:/volume1/tank/config/reading-room/
ssh -tt admin@192.168.1.204 \
  "cd /volume1/tank/config/reading-room && docker compose up -d --build"
```
The `./data` volume (DB + images) persists across rebuilds.

## Config knobs (in docker-compose.yml `environment:`)
`POLL_INTERVAL` (min), `MAX_IMAGES` per article, `FETCH_TIMEOUT` (s), `READONLY=1` to freeze writes.
