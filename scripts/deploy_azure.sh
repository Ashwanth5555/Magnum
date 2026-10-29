#!/usr/bin/env bash
#
# Deploy Magnum Now to Azure App Service. Idempotent: safe to re-run, and the
# only way the live site should ever change.
#
# The zip is an allow-list, not the repo minus some excludes. `store.py` resolves
# every path from the package root, so what has to be in here is exactly: the
# three Python packages it imports (including `generator`, which it reads config
# from), the database, `data_quality.json` (read at startup - the app will not
# boot without it), the compiled UI, and the two files App Service needs. Source,
# node_modules, CSV exports and docs are ~200 MB of things the running app never
# opens.
set -euo pipefail
cd "$(dirname "$0")/.."

RG="${RG:-rg-magnumnow-demo-ci}"
APP="${APP:-magnum-now-demo}"
ZIP="${TMPDIR:-/tmp}/magnum-now-deploy.zip"

echo "==> Building the UI"
npm run build --prefix web

echo "==> Packing $ZIP"
rm -f "$ZIP"
zip -qr "$ZIP" \
  server magnum_core generator \
  data/magnum.db data/data_quality.json \
  web/dist requirements.txt scripts/azure_startup.sh \
  -x '*/__pycache__/*' '*.pyc'
du -h "$ZIP"

echo "==> Deploying to $APP"
az webapp deploy -g "$RG" -n "$APP" --type zip --src-path "$ZIP" --timeout 1800

URL="https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
echo "==> Waiting for $URL/api/health"
# Must be "ok", not merely a 200: /api/health answers 200 with "loading" while
# the store is still building, which is the point of it.
for _ in $(seq 1 60); do
  curl -sf "$URL/api/health" 2>/dev/null | grep -q '"status":"ok"' \
    && { echo "  up: $URL"; exit 0; }
  sleep 10
done

echo "  did not come up. Logs: az webapp log tail -g $RG -n $APP" >&2
exit 1
