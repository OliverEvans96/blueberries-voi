"""Rollout vs damped-SW alpha bakeoff shards (notebook 16)."""

from __future__ import annotations

import itertools
from statistics import mean
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from blueberries_voi.sim.alpha_tune import (
    DEFAULT_DESKTOP_ALPHAS,
    evaluate_alpha_episode_outcomes,
)
from blueberries_voi.sim.shipments import default_shipments

DEFAULT_ROLLOUT_SEEDS: tuple[int, ...] = (
    42,
    7,
    101,
    2024,
    11,
    23,
    37,
    53,
    71,
    89,
    113,
    127,
)
DEFAULT_N_BURN = 14
DEFAULT_N_SCORE = 28
DEFAULT_RHO = 0.8
DEFAULT_ROLLOUT_H = 28
DEFAULT_N_ROLLOUT_PATHS = 8
DEFAULT_CANDIDATE_CASE_RADIUS = 2
BAKEOFF_ARMS: tuple[str, ...] = ("sw", "rollout")

__all__ = [
    "BAKEOFF_ARMS",
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_DESKTOP_ALPHAS",
    "DEFAULT_N_BURN",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_N_SCORE",
    "DEFAULT_RHO",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_SEEDS",
    "best_alpha_per_arm",
    "merge_rollout_eval_rows",
    "rollout_eval_job_grid",
    "run_rollout_eval",
]


def _arm_rollout_budgets(arm_id: str) -> dict[str, int]:
    if arm_id == "sw":
        return {
            "rollout_h": 2,
            "n_rollout_paths": 0,
            "candidate_case_radius": 1,
        }
    if arm_id == "rollout":
        return {
            "rollout_h": DEFAULT_ROLLOUT_H,
            "n_rollout_paths": DEFAULT_N_ROLLOUT_PATHS,
            "candidate_case_radius": DEFAULT_CANDIDATE_CASE_RADIUS,
        }
    msg = f"unsupported bakeoff arm {arm_id!r}; expected one of {BAKEOFF_ARMS}"
    raise ValueError(msg)


def run_rollout_eval(
    seed: int,
    arm_id: str,
    alpha: float,
    rho: float,
    *,
    n_burn: int = DEFAULT_N_BURN,
    n_score: int = DEFAULT_N_SCORE,
    rollout_h: int | None = None,
    n_rollout_paths: int | None = None,
    candidate_case_radius: int | None = None,
) -> dict[str, Any]:
    """Score one ``(seed, arm, alpha)`` cell via ``evaluate_alpha_episode_outcomes``."""
    budgets = _arm_rollout_budgets(arm_id)
    h = int(rollout_h if rollout_h is not None else budgets["rollout_h"])
    paths = int(
        n_rollout_paths if n_rollout_paths is not None else budgets["n_rollout_paths"]
    )
    radius = int(
        candidate_case_radius
        if candidate_case_radius is not None
        else budgets["candidate_case_radius"]
    )
    outcomes = evaluate_alpha_episode_outcomes(
        arm_id,
        float(alpha),
        int(seed),
        rho=float(rho),
        shipments=default_shipments(),
        n_burn=n_burn,
        n_score=n_score,
        rollout_h=h,
        n_rollout_paths=paths,
        candidate_case_radius=radius,
    )
    return {
        "seed": int(seed),
        "arm_id": str(arm_id),
        "alpha": float(alpha),
        "rho": float(rho),
        "profit": float(outcomes.profit),
        "waste": int(outcomes.total_waste),
        "stockout": int(outcomes.total_lost_sales),
        "n_burn": int(n_burn),
        "n_score": int(n_score),
        "rollout_h": h,
        "n_rollout_paths": paths,
        "candidate_case_radius": radius,
    }


def rollout_eval_job_grid(
    seeds: Sequence[int],
    arms: Sequence[str],
    alphas: Sequence[float],
    rho: float,
) -> list[tuple[int, str, float, float]]:
    """Cartesian product of seeds, arms, and alphas with fixed rho."""
    return [
        (int(seed), str(arm), float(alpha), float(rho))
        for seed, arm, alpha in itertools.product(seeds, arms, alphas)
    ]


def merge_rollout_eval_rows(
    shards: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Dedup on ``(seed, arm_id, alpha)``."""
    seen: set[tuple[int, str, float]] = set()
    out: list[dict[str, Any]] = []
    for shard in shards:
        key = (int(shard["seed"]), str(shard["arm_id"]), float(shard["alpha"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(shard))
    return sorted(
        out,
        key=lambda r: (r["arm_id"], float(r["alpha"]), int(r["seed"])),
    )


def best_alpha_per_arm(rows: Sequence[dict[str, Any]], arm_id: str) -> float:
    """Argmax mean profit over seeds at each alpha for one arm."""
    by_alpha: dict[float, list[float]] = {}
    for row in rows:
        if str(row["arm_id"]) != arm_id:
            continue
        alpha = float(row["alpha"])
        by_alpha.setdefault(alpha, []).append(float(row["profit"]))
    if not by_alpha:
        msg = f"no rollout_eval rows for arm {arm_id!r}"
        raise ValueError(msg)
    best_alpha = max(by_alpha, key=lambda a: mean(by_alpha[a]))
    return float(best_alpha)
