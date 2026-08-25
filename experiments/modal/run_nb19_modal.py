"""Execute notebook 19 Modal production run (probe → plan → batch)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
os.chdir(REPO)
os.environ.setdefault("BLUEBERRIES_VOI_BACKEND", "rust")
wheel_dir = REPO / "dist" / "wheel"
if wheel_dir.is_dir():
    os.environ["BLUEBERRIES_VOI_WHEEL"] = str(wheel_dir)

from blueberries_voi.experiments.batch_budget import assert_within_budget, plan_channel_joint_budget
from blueberries_voi.experiments.channel_factorial_viz import save_nb19_figures
from blueberries_voi.experiments.channel_joint import (
    all_obs_channels_product,
    channel_joint_job_grid,
    run_seed_channel_joint,
)
from blueberries_voi.experiments.modal_dispatch import run_batch
from blueberries_voi.filter.types import channels_for_preset

DATA_DIR = REPO / "experiments" / "data"
FIG_DIR = REPO / "figures" / "channel_joint"
OUT_JSON = DATA_DIR / "nb19_joint_rows.json"
CANDIDATE_SEEDS = (42, 7, 99, 101, 2024, 31415)
CHANNELS = all_obs_channels_product()
PROBE_SEED = 42
PROBE_CHANNEL = channels_for_preset("P0")


def main() -> None:
    probe_t0 = time.perf_counter()
    probe_row = run_seed_channel_joint(
        PROBE_SEED,
        PROBE_CHANNEL,
        n_burn=2,
        n_score=10,
    )
    probe_elapsed_s = time.perf_counter() - probe_t0
    print(f"probe elapsed_s={probe_elapsed_s:.1f} profit={probe_row['profit']:.2f}")

    plan = plan_channel_joint_budget(probe_elapsed_s, max_seeds=len(CANDIDATE_SEEDS))
    assert_within_budget(plan)
    seeds = tuple(CANDIDATE_SEEDS[:plan.n_seeds])
    print(plan.as_dict())

    run_t0 = time.perf_counter()
    rows = run_batch(
        "channel_joint",
        "modal",
        smoke=False,
        seeds=seeds,
        channels=CHANNELS,
        n_burn=plan.n_burn,
        n_score=plan.n_score,
        out_path=OUT_JSON,
    )
    run_wall_s = time.perf_counter() - run_t0

    expected = len(channel_joint_job_grid(seeds, CHANNELS))
    assert len(rows) == expected

    audit = {
        "shards": len(rows),
        "seeds": list(seeds),
        "n_score": plan.n_score,
        "n_burn": plan.n_burn,
        "probe_elapsed_s": probe_elapsed_s,
        "run_wall_s": run_wall_s,
        "est_cpu_hr": (len(rows) * probe_elapsed_s) / 3600.0,
    }
    print(json.dumps(audit, indent=2))

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for metric in ("mae_f", "mae_dist"):
        save_nb19_figures(rows, FIG_DIR, accuracy_column=metric)


if __name__ == "__main__":
    main()
