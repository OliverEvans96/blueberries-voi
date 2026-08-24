#!/usr/bin/env bash
# Build voi_core rustdoc and copy into the VitePress dist tree.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/docs/public/api/rust}"

cd "$ROOT"
cargo doc --no-deps -p voi_core --locked

rm -rf "$OUT"
mkdir -p "$OUT"
cp -a target/doc/voi_core "$OUT/"
# Shared assets live at target/doc/ root; voi_core/*.html references them via ../
cp -a target/doc/static.files "$OUT/"
cp -a target/doc/crates.js "$OUT/"
cp -a target/doc/src "$OUT/"
echo "rustdoc copied to $OUT/voi_core/ (+ static.files, crates.js, src/)"
