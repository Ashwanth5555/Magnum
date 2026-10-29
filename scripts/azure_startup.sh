#!/usr/bin/env bash
#
# App Service startup command. One uvicorn worker, on the port App Service hands
# us.
#
# Deliberately one worker: `store.py` builds every feature table into memory at
# startup and the process peaks around 615 MB doing it. Workers do not share
# that, so a second one would double the footprint for a read-only workload that
# has no concurrency problem to solve.
#
# It resolves its own directory rather than hard-coding /home/site/wwwroot.
# Oryx compresses the build into wwwroot/output.tar.zst and extracts the real
# app to /tmp/<hash> at boot, so at runtime wwwroot holds the tarball and
# nothing else. An absolute wwwroot path here exits 127 before uvicorn is ever
# reached.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
exec python -m uvicorn server.main:app \
  --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --log-level warning
