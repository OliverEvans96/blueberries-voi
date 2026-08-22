#!/usr/bin/env bash
# Launch the Vite studio with the Rust WASM kernel (ADR 0129 / T-144).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WEB="$ROOT/web"
WASM_PKG="$WEB/src/wasm"

export VITE_ENGINE_ADAPTER=wasm

if [[ ! -d "$WASM_PKG" ]] || ! ls "$WASM_PKG"/*.wasm >/dev/null 2>&1; then
  echo "note: wasm pkg missing under web/src/wasm/. Run ./scripts/build-wasm.sh first." >&2
fi

cd "$WEB"
exec npm run dev
