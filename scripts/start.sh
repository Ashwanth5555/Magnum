#!/usr/bin/env bash
#
# Start Magnum Now. One process, one port, nothing else running.
#
# The API serves the compiled front end out of web/dist, so there is no Node
# process, no second address, and no proxy in the path. What you run here is
# what deploys.
#
# The staleness check below is not a convenience. Without it a dist built before
# your last edit is served silently and looks like working software, which is a
# far worse failure than a build that takes two seconds.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"

needs_build() {
  [ ! -f web/dist/index.html ] && return 0
  # Any source file newer than the bundle means the bundle is a lie.
  [ -n "$(find web/src web/index.html web/public web/package.json web/vite.config.ts \
            -newer web/dist/index.html -print -quit 2>/dev/null)" ]
}

if needs_build; then
  echo "Building the UI (web/dist is missing or older than the source)…"
  npm run build --prefix web
fi

(python3 -m uvicorn server.main:app --port "$PORT" --log-level warning \
   > /tmp/magnum-now.log 2>&1 &)

for _ in $(seq 1 40); do
  curl -sf "localhost:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 1
done

if curl -sf "localhost:$PORT/api/health" >/dev/null 2>&1; then
  echo
  echo "  Magnum Now  ->  http://localhost:$PORT"
  echo "  health      ->  http://localhost:$PORT/api/health"
  echo "  logs        ->  /tmp/magnum-now.log"
  echo
else
  echo "The server did not come up. Last 20 lines of /tmp/magnum-now.log:" >&2
  tail -20 /tmp/magnum-now.log >&2
  exit 1
fi
