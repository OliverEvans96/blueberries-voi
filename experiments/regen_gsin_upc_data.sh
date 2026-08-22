#!/usr/bin/env bash
# Regenerate the GSIN/UPC investigation data for notebook 14 (post-ADR-0137 side only).
# The "before" files come from the same harness run on team/T-137/implement.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p experiments/data
cargo run -p voi_core --release --example gsin_upc_diag -- experiments/data/gsin_upc_after.json

# The §4 closed-loop half lives in a separate harness:
#   uv run --python 3.11 python experiments/regen_voi_profits.py
