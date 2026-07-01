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

## Prerequisites (Tailscale admin console — one-time)
1. **Enable HTTPS certificates** for the tailnet (Settings → Keys/DNS → enable
   MagicDNS + HTTPS).
2. **Enable Funnel** for the NAS node: add the `funnel` node attribute in the
   ACL policy, e.g.
   ```json
   "nodeAttrs": [{ "target": ["as5404t-6005-1"], "attr": ["funnel"] }]
   ```
3. Note the node's full funnel hostname — `tailscale status` on the NAS shows it,
   e.g. `as5404t-6005-1.tailXXXX.ts.net`. **This is `FUNNEL_HOST`, needed below.**

## Step 1 — Cognito (run once, from this box; AWS cli is configured)
```bash
FUNNEL_HOST=as5404t-6005-1.tailXXXX.ts.net ./cognito-setup.sh
```
Copy the four output values (ISSUER_URL, CLIENT_ID, CLIENT_SECRET, hosted-UI
domain). A temp password is emailed to you for first login.

## Step 2 — oauth2-proxy stack (Portainer, on the NAS)
1. New stack `reading-room-auth`, paste `oauth2-proxy.compose.yml`.
2. Replace the three `REPLACE_*` inline placeholders (POOL_ID, CLIENT_ID,
   FUNNEL_HOST).
3. Set stack **env vars** (keeps secrets out of git):
   - `CLIENT_SECRET` = the Cognito client secret from step 1
   - `COOKIE_SECRET` = a 32-byte base64 value: `head -c 32 /dev/urandom | base64`
     (one was generated for you in-session — paste that, or make a fresh one)
4. Deploy. Verify `http://192.168.1.204:4180` on the LAN bounces to a Cognito
   login. (If the upstream `172.17.0.1:8087` doesn't reach Reading Room on ADM,
   switch it to `http://192.168.1.204:8087`.)

## Step 3 — Tailscale Funnel (on the NAS)
Point Funnel at oauth2-proxy and turn it on:
```bash
tailscale serve --bg --https=443 http://127.0.0.1:4180
tailscale funnel 443 on
tailscale funnel status      # should show the public https URL
```
Then open `https://FUNNEL_HOST` from any machine (no Tailscale needed) → Cognito
login → Reading Room.

## Notes / gotchas
- Funnel only serves on 443 / 8443 / 10000 — 443 is used here.
- The `*.ts.net` name is fixed; a custom domain (reading-room.avgchap.com) is the
  one thing this path can't do — that would need AWS/Cloudflare fronting instead.
- Reading Room's `:8087` remains directly reachable (unauthed) on LAN/tailnet by
  design; only the public Funnel path is gated.
- To lock login to just your address, set `OAUTH2_PROXY_EMAIL_DOMAINS` to your
  domain or use `OAUTH2_PROXY_AUTHENTICATED_EMAILS_FILE`.
