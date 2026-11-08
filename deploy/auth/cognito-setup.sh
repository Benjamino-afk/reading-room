#!/usr/bin/env bash
# One-shot: create the Cognito user pool + app client + hosted-UI domain + your
# admin user for gating Reading Room behind oauth2-proxy. Region ap-southeast-2.
# Idempotent-ish: re-running create-* will error if the pool/domain already
# exists — delete or reuse rather than blindly re-running.
#
# Requires: aws cli v2 (configured), no jq (uses --query only).
# Outputs the four values oauth2-proxy needs: ISSUER_URL, CLIENT_ID,
# CLIENT_SECRET, and confirms the admin user.
set -euo pipefail

REGION=ap-southeast-2
POOL_NAME=reading-room
# Hosted-UI domain prefix — must be GLOBALLY unique across all of Cognito.
# Change if creation fails with a conflict.
DOMAIN_PREFIX="${DOMAIN_PREFIX:?set DOMAIN_PREFIX to a globally unique hosted-UI prefix}"
ADMIN_EMAIL="${ADMIN_EMAIL:?set ADMIN_EMAIL to the address that will log in}"

# The public Tailscale Funnel hostname the app is served on. REQUIRED — fill it.
# e.g. myhost.tailXXXX.ts.net  (from `tailscale status` / admin console)
FUNNEL_HOST="${FUNNEL_HOST:?set FUNNEL_HOST to the ts.net funnel hostname}"

echo ">> creating user pool ($POOL_NAME)…"
POOL_ID=$(aws cognito-idp create-user-pool --region "$REGION" \
  --pool-name "$POOL_NAME" \
  --admin-create-user-config AllowAdminCreateUserOnly=true \
  --auto-verified-attributes email \
  --username-attributes email \
  --query 'UserPool.Id' --output text)
echo "   pool id: $POOL_ID"

echo ">> creating hosted-UI domain ($DOMAIN_PREFIX)…"
aws cognito-idp create-user-pool-domain --region "$REGION" \
  --user-pool-id "$POOL_ID" --domain "$DOMAIN_PREFIX" >/dev/null

echo ">> creating app client (confidential, auth-code grant)…"
read -r CLIENT_ID CLIENT_SECRET < <(aws cognito-idp create-user-pool-client --region "$REGION" \
  --user-pool-id "$POOL_ID" \
  --client-name reading-room-oauth2proxy \
  --generate-secret \
  --allowed-o-auth-flows-user-pool-client \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --supported-identity-providers COGNITO \
  --callback-urls "https://$FUNNEL_HOST/oauth2/callback" \
  --logout-urls "https://$FUNNEL_HOST" \
  --query 'UserPoolClient.[ClientId,ClientSecret]' --output text)

echo ">> creating admin user ($ADMIN_EMAIL) — a temp password is emailed to you…"
aws cognito-idp admin-create-user --region "$REGION" \
  --user-pool-id "$POOL_ID" --username "$ADMIN_EMAIL" \
  --user-attributes Name=email,Value="$ADMIN_EMAIL" Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL >/dev/null

cat <<EOF

================  DONE — feed these into the oauth2-proxy stack  ================
  OAUTH2_PROXY_OIDC_ISSUER_URL = https://cognito-idp.$REGION.amazonaws.com/$POOL_ID
  OAUTH2_PROXY_CLIENT_ID       = $CLIENT_ID
  OAUTH2_PROXY_CLIENT_SECRET   = $CLIENT_SECRET   <-- SECRET: put in Portainer env, do NOT commit
  Hosted UI domain             = https://$DOMAIN_PREFIX.auth.$REGION.amazoncognito.com
  Admin user                   = $ADMIN_EMAIL  (temp password sent by email)
================================================================================
EOF
