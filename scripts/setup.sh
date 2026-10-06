#!/usr/bin/env bash
set -euo pipefail
SKETCH_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKETCH_ROOT"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
npm --prefix frontend ci
npm --prefix frontend run build
if [[ ! -e .env ]]; then
  cp .env.example .env
  chmod 600 .env
fi
echo 'Set OPENAI_API_KEY, ASTRA_MODEL and ISAAC_SIM_PATH in .env, then run scripts/backend.sh and scripts/sim.sh.'

