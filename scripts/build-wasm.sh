#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
rustup target add wasm32-unknown-unknown >/dev/null
export RUSTFLAGS='--cfg getrandom_backend="wasm_js"'
wasm-pack build crates/voi_wasm --target web --out-dir ../../packaging/wasm/pkg
