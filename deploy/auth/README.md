# Remote access — Tailscale Funnel + Cognito login

Exposes Reading Room to the public internet **with a Cognito login in front**,
without opening any router ports and without the remote machine needing
Tailscale. All hosting stays on the NAS; Cognito (a free user pool) is the only
AWS piece.

```
Internet ──HTTPS──▶ Tailscale Funnel (NAS node :443)
                      └─▶ oauth2-proxy :4180  ──Cognito OIDC login──▶  AWS Cognito
                            └─▶ Reading Room :8087 (host, unauthenticated, LAN/tailnet only)
```

Single-tenant: everyone who logs in shares the same reader. Sized for one user
(you) for now; adding more Cognito users gives them the *same* feeds until/unless
we do the multi-tenant refactor.

**Funnel host:** `<host>.<tailnet>.ts.net` — referred to below as `FUNNEL_HOST`.
If Tailscale is a native package on the host, run `tailscale ...` directly
(changing serve/funnel needs `sudo`); if it is containerised, prefix with
`docker exec <tailscale-container>`.

## Prerequisites (Tailscale — one-time)
1. **Enable HTTPS certificates** for the tailnet — admin console → DNS page →
   "Enable HTTPS…" button (needed for the Funnel TLS cert).
2. **Enable Funnel.** Easiest: just run the `tailscale funnel 443 on` command in
   step 3 — if it isn't enabled, the CLI prints a one-click URL that grants it.
   Or add it manually in the ACL editor (https://login.tailscale.com/admin/acls/file).
   NOTE: `nodeAttrs.target` does NOT accept a bare hostname — use `autogroup:member`
   (or a tag), not a machine name:
   ```json
   "nodeAttrs": [{ "target": ["autogroup:member"], "attr": ["funnel"] }]
   ```

## Step 1 — Cognito
Create the pool + client + hosted-UI domain + admin user with `cognito-setup.sh`
(keep the printed values in your secrets store, not in git):
```bash
FUNNEL_HOST=<host>.<tailnet>.ts.net ADMIN_EMAIL=you@example.com \
  DOMAIN_PREFIX=<globally-unique-prefix> ./cognito-setup.sh
```

## Step 2 — the Portainer stack
1. Add a stack from `oauth2-proxy.compose.yml` (Portainer → Add stack → **Upload**).
2. Set stack **env vars** (keeps host details and secrets out of git):
   - `FUNNEL_HOST` = `<host>.<tailnet>.ts.net`
   - `COGNITO_POOL_ID` = e.g. `ap-southeast-2_XXXXXXXXX`
   - `COGNITO_CLIENT_ID` = the app client id
   - `CLIENT_SECRET` = the Cognito client secret
   - `COOKIE_SECRET` = the 32-byte base64 cookie secret
3. Deploy. Verify `http://<host-ip>:4180` on the LAN bounces to a Cognito
   login. Both services share one compose network, so the upstream is the
   service name `http://reading-room:8080` — no host-gateway hop.

## Step 3 — Tailscale Funnel
Tailscale 1.98+ uses the new serve/funnel CLI: one command, target is just the
local port (Tailscale must be on the host network to reach `4180`):
```bash
sudo tailscale funnel --bg 4180
tailscale funnel status   # should show the public https URL
```
First run may refuse and print a one-click URL to enable Funnel on the tailnet —
approve it, re-run. `tailscale funnel reset` clears a stale/tailnet-only config.
(Old CLI `serve --https=443 …` + `funnel 443 on` no longer works.)
Then open `https://FUNNEL_HOST` from any machine (no Tailscale needed) → Cognito
login → Reading Room.

## Pin the allowed email (who may log in)
The compose mounts an allow-list file and sets `AUTHENTICATED_EMAILS_FILE`;
there is deliberately **no `EMAIL_DOMAINS`**, because a `*` there short-circuits
the allow-list and admits any verified Cognito user. Create the file on the host
**before** updating the stack — if the path doesn't exist Docker creates a
*directory* there and oauth2-proxy exits on boot. The config dir is root-owned:
```bash
sudo mkdir -p /volume1/tank/config/reading-room-auth
echo 'you@example.com' | sudo tee /volume1/tank/config/reading-room-auth/authenticated-emails.txt
```
One address per line; add a line + restart the container to admit someone else.
A rejected address gets a 403 *after* a successful Cognito login (expected).
Locking out the Funnel does not affect `:8087` on the LAN/tailnet.

## Notes / gotchas
- Funnel only serves on 443 / 8443 / 10000 — 443 is used here.
- The `*.ts.net` name is fixed; a custom domain is the
  one thing this path can't do — that would need AWS/Cloudflare fronting instead.
- Reading Room's `:8087` remains directly reachable (unauthed) on LAN/tailnet by
  design; only the public Funnel path is gated.
- Login is pinned to one address — see "Pin the allowed email" above.
