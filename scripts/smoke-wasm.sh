#!/usr/bin/env bash
# Build voi_wasm for wasm32 and run the Node studio-RPC contract
# (init/reset/step/step_n/act + error envelopes). Snapshot.belief.lot_counts
# must be a defined array — "ok": true is not enough.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
rustup target add wasm32-unknown-unknown >/dev/null
export RUSTFLAGS='--cfg getrandom_backend="wasm_js"'
OUT="${VOI_WASM_SMOKE_OUT:-$ROOT/target/wasm-smoke-pkg}"
wasm-pack build crates/voi_wasm --target nodejs --out-dir "$OUT"
export VOI_WASM_SMOKE_OUT="$OUT"
node "$ROOT/scripts/smoke_wasm.mjs"
