#!/usr/bin/env bash
# Launch the Vite studio with the Rust WASM kernel (ADR 0129).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WEB="$ROOT/web"
WASM_PKG="$ROOT/packaging/wasm/pkg"

export VITE_ENGINE_ADAPTER=wasm
export VITE_WASM_WORKER_URL="${VITE_WASM_WORKER_URL:-/packaging/wasm/worker.js}"
export VITE_WASM_PKG_URL="${VITE_WASM_PKG_URL:-/wasm/}"

if [[ ! -d "$WASM_PKG" ]] || ! ls "$WASM_PKG"/*.wasm >/dev/null 2>&1; then
  echo "note: wasm pkg missing under packaging/wasm/pkg/. Run ./scripts/build-wasm.sh first." >&2
fi

cd "$WEB"
exec npm run dev
