#!/usr/bin/env python3
"""Run notebook-12 SOO damped_sw Ax BO and write ``outputs/damped_sw_alpha_bo.json``.

Mirrors ``notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb`` with
``FULL_RUN=True`` (no plot cells — save-only tail).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from ax.api.client import Client
from ax.api.configs import RangeParameterConfig
from tqdm.auto import tqdm

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.model import ModelParams
from blueberries_voi.model.demand_profile import load_demand_profile
from blueberries_voi.sim.alpha_tune import (
    DEFAULT_DESKTOP_ALPHAS,
    evaluate_alpha_episode_outcomes,
    tune_alpha_grid,
)
from blueberries_voi.sim.profit import ProfitCosts
from blueberries_voi.sim.shipments import smoke_cool_shipments

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)

POLICY = "damped_sw"
TUNE_ARM = "sw"
FULL_RUN = True
ALPHA_BOUNDS = (0.1, 0.9999)
RHO_BOUNDS = (0.5, 1.0)

N_BURN, N_SCORE = 28, 28
K_BO_SEEDS = 6
N_AX_TRIALS = 20
K_VAL_SEEDS = 5
GRID_ALPHAS = DEFAULT_DESKTOP_ALPHAS

RNG = np.random.default_rng(20260817)
BO_SEEDS = [int(RNG.integers(0, 2**31 - 1)) for _ in range(K_BO_SEEDS)]
VAL_SEEDS = [int(RNG.integers(0, 2**31 - 1)) for _ in range(K_VAL_SEEDS)]

OUTPUT_JSON = REPO_ROOT / "outputs" / "damped_sw_alpha_bo.json"

UNIT_MARGIN = 2.0
WASTE_COST = 5.0
STOCKOUT_PENALTY = 3.0
costs = ProfitCosts(
    unit_margin=UNIT_MARGIN,
    waste_cost=WASTE_COST,
    stockout_penalty=STOCKOUT_PENALTY,
)

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
shipments = smoke_cool_shipments()
LEAD_TIME = 1


def evaluate_arm_outcomes(alpha: float, rho: float, root_seed: int):
    return evaluate_alpha_episode_outcomes(
        TUNE_ARM,
        float(alpha),
        int(root_seed),
        rho=float(rho),
        params=MODEL_PARAMS,
        shipments=shipments,
        costs=costs,
        n_burn=N_BURN,
        n_score=N_SCORE,
        lead_time=LEAD_TIME,
    )


def _replicate_mean_sem(values: list[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    sem = float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0
    return mean, sem


def evaluate_with_replicates(
    alpha: float,
    rho: float,
    seeds: list[int],
) -> dict[str, tuple[float, float]]:
    profits: list[float] = []
    wastes: list[float] = []
    stockouts: list[float] = []
    for seed in seeds:
        out = evaluate_arm_outcomes(alpha, rho, seed)
        profits.append(out.profit)
        wastes.append(float(out.total_waste))
        stockouts.append(float(out.total_lost_sales))
    p_mean, p_sem = _replicate_mean_sem(profits)
    w_mean, w_sem = _replicate_mean_sem(wastes)
    s_mean, s_sem = _replicate_mean_sem(stockouts)
    return {
        "episode_profit": (p_mean, p_sem),
        "total_waste": (w_mean, w_sem),
        "total_stockout": (s_mean, s_sem),
    }


def ax_parameter_configs() -> list[RangeParameterConfig]:
    return [
        RangeParameterConfig(name="alpha", parameter_type="float", bounds=ALPHA_BOUNDS),
        RangeParameterConfig(name="rho", parameter_type="float", bounds=RHO_BOUNDS),
    ]


def validation_mean(alpha: float, rho: float) -> float:
    return float(
        np.mean([evaluate_arm_outcomes(alpha, rho, s).profit for s in VAL_SEEDS])
    )


def main() -> None:
    rust_fn = getattr(rust_core, "evaluate_alpha_tune_outcomes_py", None) if rust_core else None
    print(f"policy={POLICY} rust={rust_available() and rust_fn is not None}")
    print(f"BO seeds={BO_SEEDS}")

    client_profit = Client()
    client_profit.configure_experiment(parameters=ax_parameter_configs())
    client_profit.configure_optimization(objective="episode_profit")

    trial_log_profit: list[dict[str, Any]] = []
    for _ in tqdm(range(N_AX_TRIALS), desc="Ax profit SOO"):
        trials = client_profit.get_next_trials(max_trials=1)
        trial_index, parameters = next(iter(trials.items()))
        alpha = float(parameters["alpha"])
        rho = float(parameters["rho"])
        metrics = evaluate_with_replicates(alpha, rho, BO_SEEDS)
        client_profit.complete_trial(
            trial_index=trial_index,
            raw_data={"episode_profit": metrics["episode_profit"]},
        )
        trial_log_profit.append(
            {
                "trial_index": int(trial_index),
                "alpha": alpha,
                "rho": rho,
                "mean_profit": metrics["episode_profit"][0],
                "sem_profit": metrics["episode_profit"][1],
                "mean_waste": metrics["total_waste"][0],
                "mean_stockout": metrics["total_stockout"][0],
            }
        )

    best_profit_params, _pred, best_profit_index, _name = (
        client_profit.get_best_parameterization()
    )
    best_alpha_profit = float(best_profit_params["alpha"])
    best_rho_profit = float(best_profit_params["rho"])
    print(
        f"SOO best: alpha={best_alpha_profit:.4f} rho={best_rho_profit:.4f} "
        f"(trial {best_profit_index})"
    )

    grid_rho = best_rho_profit
    grid_means: list[float] = []
    for a in tqdm(GRID_ALPHAS, desc="grid baseline"):
        profit_stats = evaluate_with_replicates(float(a), grid_rho, BO_SEEDS)[
            "episode_profit"
        ]
        grid_means.append(profit_stats[0])
    best_alpha_grid = float(GRID_ALPHAS[int(np.argmax(grid_means))])

    best_alpha_crn = tune_alpha_grid(
        TUNE_ARM,
        alphas=GRID_ALPHAS,
        root_seed=BO_SEEDS[0],
        params=MODEL_PARAMS,
        shipments=shipments,
        costs=costs,
        n_burn=N_BURN,
        n_score=N_SCORE,
    )

    val_profit = validation_mean(best_alpha_profit, best_rho_profit)
    val_grid = validation_mean(best_alpha_grid, grid_rho)

    payload: dict[str, Any] = {
        "policy": POLICY,
        "full_run": FULL_RUN,
        "rust_kernel": bool(rust_available() and rust_fn is not None),
        "alpha_bounds": list(ALPHA_BOUNDS),
        "rho_bounds": list(RHO_BOUNDS),
        "n_burn": N_BURN,
        "n_score": N_SCORE,
        "bo_seeds": BO_SEEDS,
        "val_seeds": VAL_SEEDS,
        "costs": {
            "unit_margin": UNIT_MARGIN,
            "waste_cost": WASTE_COST,
            "stockout_penalty": STOCKOUT_PENALTY,
        },
        "model_params": {
            "demand_mu": 30.0,
            "demand_vm": 2.0,
            "use_calendar_demand": USE_CALENDAR_DEMAND,
            "case_size": 8,
            "lead_time": LEAD_TIME,
            "use_abdella": False,
        },
        "best_alpha_profit_soo": best_alpha_profit,
        "best_rho_profit_soo": best_rho_profit,
        "best_alpha_grid": best_alpha_grid,
        "best_alpha_tune_alpha_grid_crn": float(best_alpha_crn),
        "validation_mean_profit_soo": val_profit,
        "validation_mean_grid": val_grid,
        "trials_profit_soo": trial_log_profit,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
