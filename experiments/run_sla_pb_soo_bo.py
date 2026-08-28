#!/usr/bin/env python3
"""Ax SOO BO for ``sla_pb`` α/ρ (notebook 12 pattern, T-163 controller bakeoff).

Writes ``outputs/sla_pb_alpha_bo.json`` and patches ``experiments/tuned_alpha.json``.

Usage::

    ./scripts/prebuild-rust.sh
    uv run --python 3.11 python experiments/run_sla_pb_soo_bo.py
    uv run --python 3.11 python experiments/run_sla_pb_soo_bo.py --local
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from ax.api.client import Client
from ax.api.configs import RangeParameterConfig
from tqdm import tqdm

from blueberries_voi.backend import rust_available
from blueberries_voi.experiments.damped_sw_soo import (
    DampedSwSooBudgets,
    aggregate_soo_shards,
    build_soo_jobs,
    evaluate_soo_jobs,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import load_demand_profile
from blueberries_voi.sim.alpha_tune import (
    DEFAULT_TUNED_ALPHA_PATH,
    load_tuned_alpha_table,
    save_tuned_alpha_table,
)
from blueberries_voi.sim.profit import ProfitCosts

ROOT = Path(__file__).resolve().parents[1]
TUNE_ARM = "sla_pb"
OUTPUT_JSON = ROOT / "experiments" / "sla_pb_alpha_bo.json"
AX_JSON = ROOT / "outputs" / "sla_pb_alpha_bo_ax_client.json"
TUNED_ALPHA_PATH = ROOT / DEFAULT_TUNED_ALPHA_PATH

FULL_RUN = True
ALPHA_BOUNDS = (0.1, 0.9999)
RHO_BOUNDS = (0.5, 1.0)

if FULL_RUN:
    N_BURN, N_SCORE = 28, 28
    K_BO_SEEDS = 6
    TOTAL_AX_TRIALS = 24
    AX_PARALLELISM = 4
    MODAL_CONCURRENCY = 32
else:
    N_BURN, N_SCORE = 2, 5
    K_BO_SEEDS = 4
    TOTAL_AX_TRIALS = 6
    AX_PARALLELISM = 2
    MODAL_CONCURRENCY = 8

UNIT_MARGIN = 2.0
WASTE_COST = 5.0
STOCKOUT_PENALTY = 3.0
DEMAND_MU = 30.0
DEMAND_VM = 2.0
CASE_SIZE = 8
LEAD_TIME = 1
USE_CALENDAR_DEMAND = True
USE_ABDELLA = False
DEMAND_PROFILE_PATH = ROOT / "data" / "freshnet" / "demand_profile.json"
_MODAL_DEMAND_PROFILE = "/data/freshnet/demand_profile.json"


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "unknown"


def _ax_parameter_configs() -> list[RangeParameterConfig]:
    return [
        RangeParameterConfig(
            name="alpha",
            parameter_type="float",
            bounds=ALPHA_BOUNDS,
        ),
        RangeParameterConfig(
            name="rho",
            parameter_type="float",
            bounds=RHO_BOUNDS,
        ),
    ]


def _soo_budgets(*, use_modal: bool) -> DampedSwSooBudgets:
    return DampedSwSooBudgets(
        n_burn=N_BURN,
        n_score=N_SCORE,
        lead_time=LEAD_TIME,
        unit_margin=UNIT_MARGIN,
        waste_cost=WASTE_COST,
        stockout_penalty=STOCKOUT_PENALTY,
        demand_mu=DEMAND_MU,
        demand_vm=DEMAND_VM,
        case_size=CASE_SIZE,
        use_calendar_demand=USE_CALENDAR_DEMAND,
        demand_profile_path=_MODAL_DEMAND_PROFILE
        if use_modal
        else str(DEMAND_PROFILE_PATH),
        use_abdella=USE_ABDELLA,
    )


def evaluate_ax_batch(
    trials: dict[int, dict[str, object]],
    seeds: list[int],
    *,
    use_modal: bool,
    budgets: DampedSwSooBudgets,
) -> dict[int, dict[str, tuple[float, float]]]:
    jobs = build_soo_jobs(trials, seeds, budgets, tune_arm=TUNE_ARM)
    shards = evaluate_soo_jobs(
        jobs,
        use_modal=use_modal,
        modal_concurrency=MODAL_CONCURRENCY,
    )
    return aggregate_soo_shards(shards)


def run_bo(*, use_modal: bool) -> dict[str, Any]:
    if not rust_available():
        print("error: build blueberries_voi._core first", file=sys.stderr)
        sys.exit(1)

    rng = np.random.default_rng(20260828)
    bo_seeds = [int(rng.integers(0, 2**31 - 1)) for _ in range(K_BO_SEEDS)]
    budgets = _soo_budgets(use_modal=use_modal)

    client = Client()
    client.configure_experiment(
        name="sla-pb-soo-modal",
        parameters=_ax_parameter_configs(),
    )
    client.configure_optimization(objective="episode_profit")

    trial_log: list[dict[str, Any]] = []
    completed = 0
    t0 = time.perf_counter()
    pbar = tqdm(total=TOTAL_AX_TRIALS, desc="Ax sla_pb SOO")
    while completed < TOTAL_AX_TRIALS:
        batch_n = min(AX_PARALLELISM, TOTAL_AX_TRIALS - completed)
        trials = client.get_next_trials(max_trials=batch_n)
        metrics_by_trial = evaluate_ax_batch(
            trials,
            bo_seeds,
            use_modal=use_modal,
            budgets=budgets,
        )
        for trial_index, parameters in trials.items():
            metrics = metrics_by_trial[int(trial_index)]
            client.complete_trial(
                trial_index=trial_index,
                raw_data={"episode_profit": metrics["episode_profit"]},
            )
            trial_log.append(
                {
                    "trial_index": int(trial_index),
                    "alpha": float(parameters["alpha"]),
                    "rho": float(parameters["rho"]),
                    "mean_profit": metrics["episode_profit"][0],
                    "sem_profit": metrics["episode_profit"][1],
                    "mean_waste": metrics["total_waste"][0],
                    "mean_stockout": metrics["total_stockout"][0],
                }
            )
        AX_JSON.parent.mkdir(parents=True, exist_ok=True)
        client.save_to_json_file(str(AX_JSON))
        completed += len(trials)
        pbar.update(len(trials))
    pbar.close()
    wall_s = time.perf_counter() - t0

    best_params, _pred, best_index, _name = client.get_best_parameterization()
    best_alpha = float(best_params["alpha"])
    best_rho = float(best_params["rho"])
    print(
        f"SOO best: α={best_alpha:.4f}, ρ={best_rho:.4f} "
        f"(trial {best_index}, wall {wall_s / 60:.1f} min)"
    )

    payload: dict[str, Any] = {
        "policy": TUNE_ARM,
        "tune_arm": TUNE_ARM,
        "full_run": FULL_RUN,
        "use_modal": use_modal,
        "modal_concurrency": MODAL_CONCURRENCY,
        "ax_parallelism": AX_PARALLELISM,
        "total_ax_trials": TOTAL_AX_TRIALS,
        "ax_client_path": str(AX_JSON.relative_to(ROOT)),
        "rust_kernel": True,
        "alpha_bounds": list(ALPHA_BOUNDS),
        "rho_bounds": list(RHO_BOUNDS),
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "bo_seeds": bo_seeds,
        "costs": {
            "unit_margin": UNIT_MARGIN,
            "waste_cost": WASTE_COST,
            "stockout_penalty": STOCKOUT_PENALTY,
        },
        "model_params": {
            "demand_mu": DEMAND_MU,
            "demand_vm": DEMAND_VM,
            "use_calendar_demand": USE_CALENDAR_DEMAND,
            "case_size": CASE_SIZE,
            "lead_time": LEAD_TIME,
            "use_abdella": USE_ABDELLA,
        },
        "best_alpha_profit_soo": best_alpha,
        "best_rho_profit_soo": best_rho,
        "trials_profit_soo": trial_log,
        "wall_seconds": wall_s,
        "generated_from_commit": _git_head(),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")

    if TUNED_ALPHA_PATH.is_file():
        raw = json.loads(TUNED_ALPHA_PATH.read_text(encoding="utf-8"))
        table = load_tuned_alpha_table(TUNED_ALPHA_PATH)
        header = dict(raw.get("header", {}))
        table[TUNE_ARM] = best_alpha
        header["sla_pb_bo_source"] = str(OUTPUT_JSON.relative_to(ROOT))
        header["sla_pb_bo_alpha"] = best_alpha
        header["sla_pb_bo_rho"] = best_rho
        save_tuned_alpha_table(TUNED_ALPHA_PATH, table, header=header)
        print(f"Patched {TUNED_ALPHA_PATH.relative_to(ROOT)} sla_pb={best_alpha:.4f}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Ax SOO BO for sla_pb alpha/rho")
    parser.add_argument(
        "--local",
        action="store_true",
        help="evaluate shards locally instead of Modal",
    )
    args = parser.parse_args()
    run_bo(use_modal=not args.local)


if __name__ == "__main__":
    main()
