#!/usr/bin/env bash
# Fast local/PR gate (<15 min): release Rust default tier + pytest not slow.
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_INCREMENTAL="${CARGO_INCREMENTAL:-0}"
cargo test --release -p voi_core -p voi_py --locked
uv run --python 3.11 pytest -n auto --no-cov
