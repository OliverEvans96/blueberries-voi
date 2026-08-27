#!/usr/bin/env bash
# Regenerate crates/voi_core/src/arrival_prior_baked.rs from data/abdella/arrival_model.json.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
cargo run --release --locked -p voi_core --bin precompute_arrival_prior
