#!/usr/bin/env bash
set -euo pipefail
SKETCH_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKETCH_ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
if [[ -z "${ISAAC_SIM_PATH:-}" || ! -x "$ISAAC_SIM_PATH/python.sh" ]]; then
  echo 'Set ISAAC_SIM_PATH in .env to your Isaac Sim installation.' >&2
  exit 1
fi
exec "$ISAAC_SIM_PATH/python.sh" "$SKETCH_ROOT/sim/draw_sim.py" "$@"

