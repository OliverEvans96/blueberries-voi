#!/usr/bin/env python3
"""Run notebook-12 SOO damped_sw Ax BO via Modal shards.

Writes ``outputs/damped_sw_alpha_bo.json``. Flat Modal parallelism across all
(trial x seed) jobs per Ax batch. Reload Ax state from
``outputs/damped_sw_alpha_bo_ax_client.json``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import numpy as np
from ax.api.client import Client
from ax.api.configs import RangeParameterConfig
from tqdm.auto import tqdm

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.experiments.damped_sw_soo import (
    DampedSwSooBudgets,
    aggregate_soo_shards,
    build_soo_jobs,
    evaluate_soo_jobs,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import load_demand_profile
from blueberries_voi.sim.profit import (
    DEFAULT_STORE_ECONOMICS,
    profit_costs_from_store_economics,
)
from blueberries_voi.sim.shipments import DEFAULT_ARRIVAL_PRODUCT, mod21_demo_shipments

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

POLICY = "damped_sw"
FULL_RUN = True
ALPHA_BOUNDS = (0.1, 0.9999)
RHO_BOUNDS = (0.5, 2.0)

N_BURN, N_SCORE = 14, 45
K_BO_SEEDS = 6
TOTAL_AX_TRIALS = 48
EXTRA_AX_TRIALS = 0
AX_PARALLELISM = 4

USE_MODAL = True
MODAL_CONCURRENCY = 100
RELOAD_AX = True

RNG = np.random.default_rng(20260817)
BO_SEEDS = [int(RNG.integers(0, 2**31 - 1)) for _ in range(K_BO_SEEDS)]

OUTPUT_JSON = REPO_ROOT / "outputs" / "damped_sw_alpha_bo.json"
AX_JSON = REPO_ROOT / "outputs" / "damped_sw_alpha_bo_ax_client.json"
_MODAL_DEMAND_PROFILE = "/data/freshnet/demand_profile.json"

costs = profit_costs_from_store_economics(DEFAULT_STORE_ECONOMICS)
UNIT_MARGIN = costs.unit_margin
WASTE_COST = costs.waste_cost
STOCKOUT_PENALTY = costs.stockout_penalty
ARRIVAL_PRODUCT = DEFAULT_ARRIVAL_PRODUCT

USE_CALENDAR_DEMAND = True
DEMAND_PROFILE_PATH = REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_demand_profile = (
    load_demand_profile(DEMAND_PROFILE_PATH) if USE_CALENDAR_DEMAND else None
)
MODEL_PARAMS = ModelParams(
    demand_mu=30.0,
    demand_vm=2.0,
    case_size=8,
    demand_profile=_demand_profile,
)
shipments = mod21_demo_shipments(ARRIVAL_PRODUCT)
LEAD_TIME = 1
DEMAND_MU = 30.0
DEMAND_VM = 2.0
CASE_SIZE = 8

SOO_BUDGETS = DampedSwSooBudgets(
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
    demand_profile_path=(
        _MODAL_DEMAND_PROFILE if USE_MODAL else str(DEMAND_PROFILE_PATH)
    ),
    arrival_product=ARRIVAL_PRODUCT,
)


def ax_parameter_configs() -> list[RangeParameterConfig]:
    return [
        RangeParameterConfig(name="alpha", parameter_type="float", bounds=ALPHA_BOUNDS),
        RangeParameterConfig(name="rho", parameter_type="float", bounds=RHO_BOUNDS),
    ]


def _completed_trial_count(client: Client) -> int:
    return sum(1 for t in client._experiment.trials.values() if t.status.is_completed)


def evaluate_ax_batch(
    trials: dict[int, dict[str, object]],
    seeds: list[int],
) -> dict[int, dict[str, tuple[float, float]]]:
    jobs = build_soo_jobs(trials, seeds, SOO_BUDGETS)
    shards = evaluate_soo_jobs(
        jobs,
        use_modal=USE_MODAL,
        modal_concurrency=MODAL_CONCURRENCY,
    )
    return aggregate_soo_shards(shards)


def main() -> None:
    rust_fn = (
        getattr(rust_core, "evaluate_alpha_tune_outcomes_py", None)
        if rust_core
        else None
    )
    print(
        f"policy={POLICY} rust={rust_available() and rust_fn is not None} "
        f"modal={USE_MODAL} trials={TOTAL_AX_TRIALS} parallelism={AX_PARALLELISM}"
    )
    print(f"BO seeds={BO_SEEDS}")

    if RELOAD_AX and AX_JSON.is_file():
        client = Client.load_from_json_file(str(AX_JSON))
        completed = _completed_trial_count(client)
        trials_to_run = (
            EXTRA_AX_TRIALS
            if EXTRA_AX_TRIALS > 0
            else max(0, TOTAL_AX_TRIALS - completed)
        )
        trial_log: list[dict[str, Any]] = []
        print(
            f"Reloaded Ax client ({completed} completed); running {trials_to_run} more"
        )
    else:
        client = Client()
        client.configure_experiment(
            name="damped-sw-soo-modal",
            parameters=ax_parameter_configs(),
        )
        client.configure_optimization(objective="episode_profit")
        trial_log = []
        trials_to_run = TOTAL_AX_TRIALS

    completed = 0
    pbar = tqdm(total=trials_to_run, desc="Ax profit SOO (Modal)")
    while completed < trials_to_run:
        batch_n = min(AX_PARALLELISM, trials_to_run - completed)
        trials = client.get_next_trials(max_trials=batch_n)
        metrics_by_trial = evaluate_ax_batch(
            cast("dict[int, dict[str, object]]", trials),
            BO_SEEDS,
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
    print(f"Saved Ax client → {AX_JSON}")

    best_profit_params, _pred, best_profit_index, _name = (
        client.get_best_parameterization()
    )
    best_alpha_profit = float(best_profit_params["alpha"])
    best_rho_profit = float(best_profit_params["rho"])
    print(
        f"SOO best: alpha={best_alpha_profit:.4f} rho={best_rho_profit:.4f} "
        f"(trial {best_profit_index})"
    )

    payload: dict[str, Any] = {
        "policy": POLICY,
        "full_run": FULL_RUN,
        "use_modal": USE_MODAL,
        "modal_concurrency": MODAL_CONCURRENCY,
        "ax_parallelism": AX_PARALLELISM,
        "total_ax_trials": TOTAL_AX_TRIALS,
        "ax_client_path": str(AX_JSON.relative_to(REPO_ROOT)),
        "rust_kernel": bool(rust_available() and rust_fn is not None),
        "alpha_bounds": list(ALPHA_BOUNDS),
        "rho_bounds": list(RHO_BOUNDS),
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "bo_seeds": BO_SEEDS,
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
            "arrival_product": ARRIVAL_PRODUCT,
        },
        "best_alpha_profit_soo": best_alpha_profit,
        "best_rho_profit_soo": best_rho_profit,
        "trials_profit_soo": trial_log,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
