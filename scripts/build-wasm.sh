#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
rustup target add wasm32-unknown-unknown >/dev/null
if ! command -v wasm-pack >/dev/null 2>&1; then
  echo "wasm-pack not found; installing…" >&2
  curl -fsSL https://rustwasm.github.io/wasm-pack/installer/init.sh | sh -s -- -f
fi
export RUSTFLAGS='--cfg getrandom_backend="wasm_js"'
WEB_WASM="$ROOT/web/src/wasm"
LEGACY_PKG="$ROOT/packaging/wasm/pkg"
wasm-pack build crates/voi_wasm --release --target web --out-dir "$WEB_WASM"
mkdir -p "$(dirname "$LEGACY_PKG")"
rm -rf "$LEGACY_PKG"
cp -a "$WEB_WASM" "$LEGACY_PKG"
