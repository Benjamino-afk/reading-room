# Deploy Reading Room

The image is built automatically by GitHub and stored online. Your Docker host
just downloads and runs it. Four steps.

## 1. Registry access
The GHCR image is **public**, so no login or token is needed to pull it.
(If you fork this and keep your package private, add a GHCR registry in
Portainer → **Registries** → **Custom**: URL `ghcr.io`, your GitHub username,
and a PAT with `read:packages` as the password.)

## 2. Add the stack in Portainer
Portainer → **Stacks** → **Add stack** → name it `reading-room`.

Open the file **`docker-compose.portainer.yml`** from this repo (the *raw* file, not
this README), select all, copy, and paste it into the Portainer web editor → **Deploy
the stack**. Copying from the raw file avoids dragging in markdown code-fence lines.

For reference, the file contains exactly this (no ` ``` ` fences, no `---` separators):

```yaml
services:
  reading-room:
    image: ghcr.io/benjamino-afk/reading-room:latest
    container_name: reading-room
    network_mode: bridge
    ports:
      - "8087:8080"
    volumes:
      - /volume1/tank/config/reading-room/data:/data
    restart: unless-stopped
```

## 3. Open it
- On the LAN: **http://<host-ip>:8087**
- Anywhere (Tailscale): **http://<host>:8087**
- From the internet: **https://<host>.<tailnet>.ts.net** (Cognito-gated; the
  two ports above are unauthenticated by design and LAN/tailnet only)

## 4. Add your first feed
Click **+ Add feed**, paste a site or feed URL (e.g. `https://hnrss.org/frontpage`),
hit **Fetch & add**. Done.

## Updating later
When the code changes (a push to `main`), GitHub rebuilds the image. To get the
new version: Portainer → the `reading-room` stack → **Update the stack**
→ tick **Re-pull image** → **Update**.

## Settings (optional)
Add these under the service if you want to change defaults (all optional):
```yaml
    environment:
      POLL_INTERVAL: "30"   # how often to check feeds, in minutes
      MAX_IMAGES: "12"      # images saved per article
```
Your articles and images live in `/volume1/tank/config/reading-room/data` and
survive updates.
