#!/usr/bin/env python3
"""Regenerate ``experiments/data/voi_profits_after.json`` for notebook 14 §4.

The closed-loop half of the GSIN/UPC study had no committed harness — the numbers
in ``voi_profits_before.json`` were produced by an ad-hoc call. This script pins
the budgets the data README documents (``n_burn=2 n_score=30 filter_n=24``, seeds
42/7/101/2024) so the "after" side can be regenerated at any tip.

Usage::

    uv run --python 3.11 python experiments/regen_voi_profits.py
"""

from __future__ import annotations

import json
from pathlib import Path

from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "data" / "voi_profits_after.json"

SEEDS = (42, 7, 101, 2024)
BETA = 2.0  # ModelParams::default().beta
N_BURN = 2
N_SCORE = 30
FILTER_N = 24


def main() -> None:
    lines: list[str] = []
    for seed in SEEDS:
        table = run_voi_crn_cell(
            beta=BETA,
            root_seed=seed,
            n_burn=N_BURN,
            n_score=N_SCORE,
            filter_n=FILTER_N,
        )
        for name in VOI_SCENARIOS:
            seed_j = json.dumps(seed)
            name_j = json.dumps(name)
            profit = float(table[name])
            lines.append(
                f'{{"seed":{seed_j},"scenario":{name_j},"profit":{profit:.4f}}}'
            )
        summary = "  ".join(f"{n}={table[n]:.1f}" for n in VOI_SCENARIOS)
        print(f"seed {seed}: {summary}")

    OUT.write_text("[\n  " + ",\n  ".join(lines) + "\n]\n")
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(lines)} rows)")


if __name__ == "__main__":
    main()
