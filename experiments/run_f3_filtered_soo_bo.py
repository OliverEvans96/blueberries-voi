#!/usr/bin/env python3
"""Ax SOO BO for constant / sw / sla_pb under filtered F3 beliefs (T-163).

Scores shards via ``run_controller_eval`` (belief_world=filtered, preset F3), not
oracle ``evaluate_alpha_episode_outcomes``.

Writes ``experiments/f3_filtered_alpha_bo.json`` and
``experiments/tuned_alpha_f3_filtered.json``.

BO episode budget: ``n_burn=2``, ``n_score=28`` (faster than 45-day bakeoff;
bakeoff uses ``n_score=45`` with the tuned params).

Usage::

    ./scripts/prebuild-rust.sh
    uv run --python 3.11 python experiments/run_f3_filtered_soo_bo.py
    uv run --python 3.11 python experiments/run_f3_filtered_soo_bo.py --local
    uv run --python 3.11 python experiments/run_f3_filtered_soo_bo.py --smoke
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
from ax.api.client import Client
from ax.api.configs import RangeParameterConfig
from tqdm import tqdm

from blueberries_voi.backend import rust_available
from blueberries_voi.experiments.controller_bakeoff import FILTERED_ARMS
from blueberries_voi.experiments.damped_sw_soo import (
    DampedSwSooBudgets,
    aggregate_soo_shards,
    build_soo_jobs,
    evaluate_soo_jobs,
)
from blueberries_voi.sim.alpha_tune import (
    load_tuned_alpha_table,
    save_tuned_alpha_table,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "experiments" / "f3_filtered_alpha_bo.json"
TUNED_ALPHA_F3_PATH = ROOT / "experiments" / "tuned_alpha_f3_filtered.json"

FULL_RUN = True
ALPHA_BOUNDS = (0.1, 0.9999)
RHO_BOUNDS = (0.5, 1.0)
CONSTANT_FIXED_RHO = 0.8

if FULL_RUN:
    N_BURN, N_SCORE = 2, 28
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
USE_ABDELLA = True
DEMAND_PROFILE_PATH = ROOT / "data" / "freshnet" / "demand_profile.json"
_MODAL_DEMAND_PROFILE = "/data/freshnet/demand_profile.json"
OBS_PRESET = "F3"


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "unknown"


def _ax_parameter_configs(arm: str) -> list[RangeParameterConfig]:
    configs = [
        RangeParameterConfig(
            name="alpha",
            parameter_type="float",
            bounds=ALPHA_BOUNDS,
        ),
    ]
    if arm != "constant":
        configs.append(
            RangeParameterConfig(
                name="rho",
                parameter_type="float",
                bounds=RHO_BOUNDS,
            )
        )
    return configs


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
        belief_world="filtered",
        obs_preset=OBS_PRESET,
    )


def evaluate_ax_batch(
    arm: str,
    trials: dict[int, dict[str, object]],
    seeds: list[int],
    *,
    use_modal: bool,
    budgets: DampedSwSooBudgets,
) -> dict[int, dict[str, tuple[float, float]]]:
    fixed_rho = CONSTANT_FIXED_RHO
    trial_params: dict[int, dict[str, object]] = {}
    for trial_index, params in trials.items():
        alpha_raw = params["alpha"]
        if not isinstance(alpha_raw, (int, float, str)):
            msg = f"alpha must be numeric, got {type(alpha_raw)!r}"
            raise TypeError(msg)
        alpha = float(alpha_raw)
        if arm != "constant":
            rho_raw = params.get("rho", fixed_rho)
            if not isinstance(rho_raw, (int, float, str)):
                msg = f"rho must be numeric, got {type(rho_raw)!r}"
                raise TypeError(msg)
            rho = float(rho_raw)
        else:
            rho = fixed_rho
        trial_params[int(trial_index)] = {"alpha": alpha, "rho": rho}
    jobs = build_soo_jobs(trial_params, seeds, budgets, tune_arm=arm)
    shards = evaluate_soo_jobs(
        jobs,
        use_modal=use_modal,
        modal_concurrency=MODAL_CONCURRENCY,
    )
    return aggregate_soo_shards(shards)


def run_arm_bo(
    arm: str,
    *,
    use_modal: bool,
    smoke: bool,
    bo_seeds: list[int],
    budgets: DampedSwSooBudgets,
) -> dict[str, Any]:
    total_trials = 2 if smoke else TOTAL_AX_TRIALS
    parallelism = 1 if smoke else AX_PARALLELISM
    ax_path = ROOT / "outputs" / f"f3_filtered_{arm}_ax_client.json"

    client = Client()
    client.configure_experiment(
        name=f"f3-filtered-{arm}-soo",
        parameters=_ax_parameter_configs(arm),
    )
    client.configure_optimization(objective="episode_profit")

    trial_log: list[dict[str, Any]] = []
    completed = 0
    t0 = time.perf_counter()
    pbar = tqdm(total=total_trials, desc=f"Ax F3 {arm} SOO")
    while completed < total_trials:
        batch_n = min(parallelism, total_trials - completed)
        raw_trials = client.get_next_trials(max_trials=batch_n)
        trials = cast("dict[int, dict[str, object]]", dict(raw_trials))
        metrics_by_trial = evaluate_ax_batch(
            arm,
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
            entry: dict[str, Any] = {
                "trial_index": int(trial_index),
                "alpha": float(parameters["alpha"]),
                "mean_profit": metrics["episode_profit"][0],
                "sem_profit": metrics["episode_profit"][1],
                "mean_waste": metrics["total_waste"][0],
                "mean_stockout": metrics["total_stockout"][0],
            }
            if arm != "constant":
                entry["rho"] = float(parameters["rho"])
            else:
                entry["rho"] = CONSTANT_FIXED_RHO
            trial_log.append(entry)
        ax_path.parent.mkdir(parents=True, exist_ok=True)
        client.save_to_json_file(str(ax_path))
        completed += len(trials)
        pbar.update(len(trials))
    pbar.close()
    wall_s = time.perf_counter() - t0

    best_params, _pred, best_index, _name = client.get_best_parameterization()
    best_alpha = float(best_params["alpha"])
    best_rho = float(best_params["rho"]) if arm != "constant" else CONSTANT_FIXED_RHO
    print(
        f"F3 {arm} best: alpha={best_alpha:.4f}, rho={best_rho:.4f} "
        f"(trial {best_index}, wall {wall_s / 60:.1f} min)"
    )
    return {
        "tune_arm": arm,
        "best_alpha": best_alpha,
        "best_rho": best_rho,
        "best_trial_index": int(best_index),
        "total_ax_trials": total_trials,
        "ax_client_path": str(ax_path.relative_to(ROOT)),
        "trials_profit_soo": trial_log,
        "wall_seconds": wall_s,
    }


def run_bo(*, use_modal: bool, smoke: bool) -> dict[str, Any]:
    if not rust_available():
        print("error: build blueberries_voi._core first", file=sys.stderr)
        sys.exit(1)

    rng = np.random.default_rng(20260828)
    bo_seeds = [int(rng.integers(0, 2**31 - 1)) for _ in range(K_BO_SEEDS)]
    budgets = _soo_budgets(use_modal=use_modal)
    arms = tuple(FILTERED_ARMS)
    if smoke:
        arms = (arms[0],)

    arm_results: dict[str, Any] = {}
    total_wall = 0.0
    for arm in arms:
        arm_results[arm] = run_arm_bo(
            arm,
            use_modal=use_modal,
            smoke=smoke,
            bo_seeds=bo_seeds,
            budgets=budgets,
        )
        total_wall += float(arm_results[arm]["wall_seconds"])

    payload: dict[str, Any] = {
        "belief_world": "filtered",
        "obs_preset": OBS_PRESET,
        "full_run": FULL_RUN and not smoke,
        "smoke": smoke,
        "use_modal": use_modal,
        "modal_concurrency": MODAL_CONCURRENCY,
        "ax_parallelism": AX_PARALLELISM,
        "total_ax_trials_per_arm": 2 if smoke else TOTAL_AX_TRIALS,
        "alpha_bounds": list(ALPHA_BOUNDS),
        "rho_bounds": list(RHO_BOUNDS),
        "constant_fixed_rho": CONSTANT_FIXED_RHO,
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "bo_episode_note": (
            "BO scored at n_score=28; controller bakeoff uses n_score=45"
        ),
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
        "arms": arm_results,
        "wall_seconds": total_wall,
        "generated_from_commit": _git_head(),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")

    table = {arm: float(arm_results[arm]["best_alpha"]) for arm in arms}
    rhos = {arm: float(arm_results[arm]["best_rho"]) for arm in arms}
    header: dict[str, Any] = {
        "belief_world": "filtered",
        "obs_preset": OBS_PRESET,
        "bo_source": str(OUTPUT_JSON.relative_to(ROOT)),
        "rhos": rhos,
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "bo_episode_note": payload["bo_episode_note"],
        "generated_from_commit": _git_head(),
    }
    save_tuned_alpha_table(TUNED_ALPHA_F3_PATH, table, header=header)
    print(f"Wrote {TUNED_ALPHA_F3_PATH.relative_to(ROOT)}")

    if TUNED_ALPHA_F3_PATH.is_file():
        loaded = load_tuned_alpha_table(TUNED_ALPHA_F3_PATH)
        assert loaded == table

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ax SOO BO for constant/sw/sla_pb under filtered F3"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="evaluate shards locally instead of Modal",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="2 Ax trials per arm, constant arm only if combined with --arm",
    )
    args = parser.parse_args()
    run_bo(use_modal=not args.local, smoke=args.smoke)


if __name__ == "__main__":
    main()
