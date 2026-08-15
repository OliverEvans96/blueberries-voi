#!/usr/bin/env bash
# Launch the Vite studio with one engine adapter. No silent default.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WEB="$ROOT/web"
WASM_PKG="$ROOT/packaging/wasm/pkg"
DEFAULT_WHEEL_URL="/wheels/blueberries_voi-0.1.0-py3-none-any.whl"
DEFAULT_API_BASE="${VITE_ENGINE_API_BASE_URL:-http://127.0.0.1:8000}"

usage() {
  cat <<'EOF'
Usage: ./scripts/studio.sh --wasm | --http | --pyodide

  --wasm     Rust kernel (VITE_ENGINE_ADAPTER=wasm). No FastAPI.
             Worker /packaging/wasm/worker.js, pkg /wasm/.
             Build first with ./scripts/build-wasm.sh if packaging/wasm/pkg is missing.

  --http     FastAPI EngineSession (VITE_ENGINE_ADAPTER=http).
             API base: $VITE_ENGINE_API_BASE_URL or http://127.0.0.1:8000
             (if :8000 is taken, e.g. OpenHands, start uvicorn on 8001 and export
             VITE_ENGINE_API_BASE_URL=http://127.0.0.1:8001).

  --pyodide  In-browser Python (VITE_ENGINE_ADAPTER=pyodide). No FastAPI.
             Local wheel /wheels/... so GitHub Release CORS is not required.
             Build first with: uv run python scripts/build_slim_wheel.py

EOF
  exit 2
}

MODE=""
for arg in "$@"; do
  case "$arg" in
    --wasm|--http|--pyodide)
      if [[ -n "$MODE" ]]; then
        echo "error: pick exactly one of --wasm --http --pyodide" >&2
        usage
      fi
      MODE="${arg#--}"
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "error: unknown argument: $arg" >&2
      usage
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  usage
fi

export VITE_ENGINE_ADAPTER="$MODE"

case "$MODE" in
  wasm)
    export VITE_WASM_WORKER_URL="${VITE_WASM_WORKER_URL:-/packaging/wasm/worker.js}"
    export VITE_WASM_PKG_URL="${VITE_WASM_PKG_URL:-/wasm/}"
    if [[ ! -d "$WASM_PKG" ]] || ! ls "$WASM_PKG"/*.wasm >/dev/null 2>&1; then
      echo "note: wasm pkg missing under packaging/wasm/pkg/. Run ./scripts/build-wasm.sh first." >&2
    fi
    ;;
  http)
    export VITE_ENGINE_API_BASE_URL="$DEFAULT_API_BASE"
    ;;
  pyodide)
    export VITE_PYODIDE_WORKER_URL="${VITE_PYODIDE_WORKER_URL:-/packaging/pyodide/worker.js}"
    export VITE_PYODIDE_WHEEL_URL="${VITE_PYODIDE_WHEEL_URL:-$DEFAULT_WHEEL_URL}"
    ;;
esac

cd "$WEB"
exec npm run dev
