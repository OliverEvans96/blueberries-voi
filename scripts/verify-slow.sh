#!/usr/bin/env bash
# Slow tier: Rust #[ignore] tests + Python @slow (PyO3 CLI/bench only).
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_INCREMENTAL="${CARGO_INCREMENTAL:-0}"
cargo test --release -p voi_core -p voi_py --locked -- --ignored
uv run --python 3.11 pytest -m slow -v
