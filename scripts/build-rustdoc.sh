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
# cargo doc also writes target/doc/search.index and crates.js at target/doc/ root;
# voi_core pages are self-contained under voi_core/ for our bundle layout.
echo "rustdoc copied to $OUT/voi_core/"
