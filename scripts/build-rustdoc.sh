#!/usr/bin/env bash
# Build rustdoc for the whole workspace (voi_core, voi_py, voi_wasm) and copy it,
# plus a hand-authored landing page, into the VitePress dist tree.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/docs/public/api/rust}"

cd "$ROOT"
cargo doc --no-deps --workspace --locked

rm -rf "$OUT"
mkdir -p "$OUT"

# Per-crate output. voi_py's [lib] name is `_core` (it compiles to
# blueberries_voi._core), so that's the directory name rustdoc gives it.
cp -a target/doc/voi_core "$OUT/"
cp -a target/doc/_core "$OUT/"
cp -a target/doc/voi_wasm "$OUT/"

# Shared assets: every crate's *.html references these via ../.
cp -a target/doc/static.files "$OUT/"
cp -a target/doc/crates.js "$OUT/"
cp -a target/doc/src "$OUT/"
cp -a target/doc/src-files.js "$OUT/"
cp -a target/doc/search.index "$OUT/"
cp -a target/doc/help.html "$OUT/"
cp -a target/doc/settings.html "$OUT/"
if [ -d target/doc/trait.impl ]; then
  cp -a target/doc/trait.impl "$OUT/"
fi

# Landing page introducing the three crates in project context; the crates'
# own rustdoc index pages (their crate-level `//!` docs) are the deep-dive.
cp "$ROOT/docs/.vitepress/rustdoc-index.html" "$OUT/index.html"

echo "rustdoc copied to $OUT/{voi_core,_core,voi_wasm}/ (+ shared assets, index.html)"
