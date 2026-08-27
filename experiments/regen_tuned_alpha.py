#!/usr/bin/env python3
"""Regenerate ``experiments/tuned_alpha.json`` (T-150 recal scope).

Tunes constant, rung0, and damped_sw (``sw``) on Abdella with desktop budgets.
``rollout`` alpha is inherited from ``sw`` (not independently tuned). ``dp`` is a
placeholder until T-031.

Usage::

    uv run --python 3.11 maturin develop --release -m crates/voi_py/Cargo.toml
    uv run --python 3.11 python experiments/regen_tuned_alpha.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from blueberries_voi.backend import rust_available
from blueberries_voi.sim.alpha_tune import (
    DEFAULT_DESKTOP_ALPHAS,
    DEFAULT_TUNED_ALPHA_PATH,
    LADDER_ALPHA_ARMS,
    save_tuned_alpha_table,
    tune_alpha_grid,
)
from blueberries_voi.sim.shipments import default_shipments

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / DEFAULT_TUNED_ALPHA_PATH

PHYSICS_EPOCH = "t150-f-native-arrival"
ROOT_SEED = 42
N_BURN = 14
N_SCORE = 28
TUNE_ARMS = ("constant", "rung0", "sw", "sla_pb", "sla_mc")
PLACEHOLDER_DP_ALPHA = 0.9
ROLLOUT_INHERIT_NOTE = (
    "inherited from damped_sw (rollout builds on damped_sw); not independently tuned"
)


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "unknown"


def main() -> None:
    if not rust_available():
        print(
            "error: build blueberries_voi._core first (maturin develop --release)",
            file=sys.stderr,
        )
        sys.exit(1)

    ships = default_shipments()
    tuned: dict[str, float] = {}
    arm_seconds: dict[str, float] = {}

    for arm in TUNE_ARMS:
        t0 = time.perf_counter()
        best = tune_alpha_grid(
            arm,
            alphas=DEFAULT_DESKTOP_ALPHAS,
            root_seed=ROOT_SEED,
            shipments=ships,
            n_burn=N_BURN,
            n_score=N_SCORE,
        )
        elapsed = time.perf_counter() - t0
        arm_seconds[arm] = elapsed
        tuned[arm] = float(best)
        print(f"  {arm}: {best:.3f}  ({elapsed / 60:.1f} min)")

    sw_alpha = tuned["sw"]
    tuned["rollout"] = sw_alpha
    tuned["dp"] = PLACEHOLDER_DP_ALPHA
    print(f"  rollout: {sw_alpha:.3f}  (inherited from sw, not tuned)")
    print(f"  dp: {PLACEHOLDER_DP_ALPHA:.3f}  (placeholder)")

    header = {
        "physics_epoch": PHYSICS_EPOCH,
        "generated_from_commit": _git_head(),
        "script": "experiments/regen_tuned_alpha.py",
        "shipments": "default_shipments (Abdella)",
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "alphas": list(DEFAULT_DESKTOP_ALPHAS),
        "root_seed": ROOT_SEED,
        "tuned_arms": list(TUNE_ARMS),
        "rollout_alpha_source": ROLLOUT_INHERIT_NOTE,
        "arm_wall_seconds": {k: round(v, 1) for k, v in arm_seconds.items()},
        "rollout_not_tuned": True,
    }
    save_tuned_alpha_table(OUT, {k: tuned[k] for k in LADDER_ALPHA_ARMS}, header=header)
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    total_min = sum(arm_seconds.values()) / 60
    print(f"total tuned-arm wall: {total_min:.1f} min")


if __name__ == "__main__":
    main()
