#!/usr/bin/env bash
# Prebuild release Rust test binaries + optional PyO3 extension (local dev).
set -euo pipefail
cd "$(dirname "$0")/.."
cargo test --release -p voi_core -p voi_py --locked --no-run
if command -v uv >/dev/null 2>&1; then
  uv run maturin develop --release -m crates/voi_py/Cargo.toml
fi
