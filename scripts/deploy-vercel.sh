#!/usr/bin/env bash
# Deploy KOMEK DAMU bot to Vercel (production) and register webhooks.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${VERCEL_TOKEN:-}" ]]; then
  echo "Set VERCEL_TOKEN"
  exit 1
fi

export VERCEL_ORG_ID="${VERCEL_ORG_ID:-team_XvdeejTJMqlLFFaRhoG1E13Y}"
export VERCEL_PROJECT_ID="${VERCEL_PROJECT_ID:-prj_m1mEnj8dwl0kk0g9spQEoXNgimkJ}"

echo "==> Deploying to Vercel production..."
DEPLOY_URL=$(vercel deploy --prod --yes --token "$VERCEL_TOKEN" 2>&1 | tee /dev/stderr | grep -Eo 'https://[a-zA-Z0-9.-]+\.vercel\.app' | tail -1)

if [[ -z "$DEPLOY_URL" ]]; then
  DEPLOY_URL="https://komek-damu-bot.vercel.app"
fi

echo "==> Production URL: $DEPLOY_URL"
echo "==> Registering Telegram webhook via /setup ..."
curl -fsS "${DEPLOY_URL}/setup" | head -c 2000
echo

if [[ -n "${GREEN_API_INSTANCE_ID:-}" && -n "${GREEN_API_TOKEN:-}" ]]; then
  WA_URL="${DEPLOY_URL}/webhook/whatsapp"
  echo "==> Green API webhook: $WA_URL"
  GREEN_HOST="${GREEN_API_URL:-https://7107.api.greenapi.com}"
  GREEN_HOST="${GREEN_HOST%/}"
  WA_AUTH="${GREEN_API_WEBHOOK_TOKEN:-}"
  curl -fsS -X POST \
    "${GREEN_HOST}/waInstance${GREEN_API_INSTANCE_ID}/setSettings/${GREEN_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"webhookUrl\":\"${WA_URL}\",\"webhookUrlToken\":\"${WA_AUTH}\",\"incomingWebhook\":\"yes\",\"outgoingWebhook\":\"yes\"}" \
    | head -c 500
  echo
fi

echo "Done. WEBHOOK_BASE_URL=$DEPLOY_URL"
