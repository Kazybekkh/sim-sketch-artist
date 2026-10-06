#!/usr/bin/env bash
set -euo pipefail
SKETCH_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKETCH_ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
SKETCH_TUNNEL_BIN="${CLOUDFLARED_BIN:-cloudflared}"
if ! command -v "$SKETCH_TUNNEL_BIN" >/dev/null; then
  echo 'Install cloudflared or set CLOUDFLARED_BIN to its path.' >&2
  exit 1
fi
exec "$SKETCH_TUNNEL_BIN" tunnel --url "http://127.0.0.1:${PORT:-8000}" --no-autoupdate

