# Deploy Reading Room

The image is built automatically by GitHub and stored online. The NAS just
downloads and runs it. Four steps.

## 1. Let the NAS log in to GitHub (one time only)
The image is private, so the NAS needs a read-only token to download it.

**a. Make a token:** open this link (scope is pre-ticked) →
https://github.com/settings/tokens/new?scopes=read:packages&description=NAS+GHCR
→ **Generate token** → copy it. (Save it in `Documents\AIwork\Secrets` so you don't lose it.)

**b. Add it to Portainer:** Portainer → **Registries** → **Add registry** → **Custom** →
- Name: `ghcr`
- Registry URL: `ghcr.io`
- Username: `Benjamino-afk`
- Password: the token from step a
→ **Add registry**.

You only ever do this once.

## 2. Add the stack in Portainer
Portainer → **Stacks** → **Add stack** → name it `reading-room` → paste this in the
web editor → **Deploy the stack**:

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
- On the LAN: **http://192.168.1.204:8087**
- Anywhere (Tailscale): **http://as5404t-6005-1:8087**

## 4. Add your first feed
Click **+ Add feed**, paste a site or feed URL (e.g. `https://hnrss.org/frontpage`),
hit **Fetch & add**. Done.

---

## Updating later
When the code changes (a push to `main`), GitHub rebuilds the image. To get the
new version on the NAS: Portainer → the `reading-room` stack → **Update the stack**
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
