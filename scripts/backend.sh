#!/usr/bin/env bash
set -euo pipefail
SKETCH_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKETCH_ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
exec "$SKETCH_ROOT/.venv/bin/python" -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}"

