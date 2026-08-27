"""CTL-05 five-point M2 ladder harness (outside ``controller/``).

Evaluates constant -> Rung 0 -> SW -> SW+rollout -> toy DP under a shared CRN
``root_seed``, gated on the T-029 tuned-alpha artifact. Numeric results land under
``experiments/`` (never inside ``controller/``). Production backend remains
``counts_only`` (ADR 0105).

T-083: profit arms attach ``DEFAULT_ORDER_SCHEDULE`` (orders Sun/Tue/Thu) and
burn-in is interpreted under **periodic** MWF age, not daily-stationary only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueberries_voi.controller.toy_dp import solve_toy_dp
from blueberries_voi.filter import PRODUCTION_BACKEND
from blueberries_voi.model import ModelParams
from blueberries_voi.sim.alpha_tune import (
    assert_ladder_profit_claim_allowed,
    evaluate_alpha_episode_profit,
    require_tuned_alpha_table,
)
from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.sim.bakeoff_rollout import RolloutPolicy
from blueberries_voi.sim.episode import run_closed_loop_episode
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, episode_profit
from blueberries_voi.sim.shipments import default_shipments

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from blueberries_voi.model.abdella import ShipmentTrace

LADDER_POINTS: tuple[str, ...] = (
    "constant",
    "rung0",
    "sw",
    "sla_pb",
    "sla_mc",
    "rollout",
    "dp",
)

# Production counts-only backend (ADR 0105); never silently select joint / age-MF.
LADDER_PRODUCTION_BACKEND: str = "counts_only"
DEFAULT_LADDER_RESULT_PATH: str = "experiments/m2_ladder_result.json"

_CI_N_BURN: int = 2
_CI_N_SCORE: int = 5
_CI_ROLLOUT_H: int = 2
_CI_N_ROLLOUT_PATHS: int = 1

__all__ = [
    "DEFAULT_LADDER_RESULT_PATH",
    "LADDER_POINTS",
    "LADDER_PRODUCTION_BACKEND",
    "LadderResult",
    "run_m2_ladder",
]


@dataclass(frozen=True)
class LadderResult:
    """Numeric CTL-05 ladder evaluation under a shared root seed."""

    points: tuple[str, ...]
    profits: Mapping[str, float]
    production_backend: str = LADDER_PRODUCTION_BACKEND
    artifact_paths: tuple[Path, ...] = field(default_factory=tuple)
    alphas: Mapping[str, float] = field(default_factory=dict)
    root_seed: int = 0


def _evaluate_rollout_profit(
    alpha: float,
    root_seed: int,
    *,
    params: ModelParams,
    costs: ProfitCosts,
    shipments: Sequence[ShipmentTrace],
    n_burn: int,
    n_score: int,
    lead_time: int,
) -> float:
    base = DampedSurvivalWeightedPolicy(
        alpha=float(alpha),
        params=params,
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    policy = RolloutPolicy(
        base_policy=base,
        params=params,
        root_seed=int(root_seed),
        run_id="m2-ladder-rollout",
        H=_CI_ROLLOUT_H,
        n_rollout_paths=_CI_N_ROLLOUT_PATHS,
        lead_time=lead_time,
    )
    episode = run_closed_loop_episode(
        policy,
        shipments=list(shipments),
        params=params,
        root_seed=int(root_seed),
        run_id="m2-ladder-rollout",
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    return float(episode_profit(episode, costs))


def _evaluate_dp_profit() -> float:
    """Toy-DP optimum value on the CTL-06 certificate instance (numeric arm)."""
    toy = solve_toy_dp(schedule=DEFAULT_ORDER_SCHEDULE)
    key = (0, toy.initial_state)
    return float(toy.value_table[key])


def _write_ladder_artifact(
    path: Path,
    *,
    profits: Mapping[str, float],
    alphas: Mapping[str, float],
    root_seed: int,
    production_backend: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "points": list(LADDER_POINTS),
        "profits": {k: float(profits[k]) for k in LADDER_POINTS},
        "alphas": {k: float(alphas[k]) for k in LADDER_POINTS},
        "root_seed": int(root_seed),
        "production_backend": production_backend,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def run_m2_ladder(
    *,
    alpha_table_path: str | Path,
    root_seed: int,
    out_dir: str | Path | None = None,
    params: ModelParams | None = None,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    n_burn: int = _CI_N_BURN,
    n_score: int = _CI_N_SCORE,
    lead_time: int = 1,
) -> LadderResult:
    """Evaluate the five CTL-05 ladder points under shared ``root_seed``.

    Profit claims require a complete T-029 tuned-alpha table
    (``assert_ladder_profit_claim_allowed`` / ``require_tuned_alpha_table``).
    """
    # Hard gate: missing / incomplete tuned-alpha artifact fails the harness.
    assert_ladder_profit_claim_allowed(alpha_table_path)
    alphas = require_tuned_alpha_table(alpha_table_path)

    if PRODUCTION_BACKEND != "counts_only":
        msg = (
            "ladder requires production backend counts_only "
            f"(got {PRODUCTION_BACKEND!r})"
        )
        raise RuntimeError(msg)
    backend = LADDER_PRODUCTION_BACKEND

    p = params or ModelParams()
    cost = costs if costs is not None else DEFAULT_PROFIT_COSTS
    ships = list(shipments) if shipments is not None else default_shipments()

    profits: dict[str, float] = {}
    for arm in ("constant", "rung0", "sw"):
        profits[arm] = float(
            evaluate_alpha_episode_profit(
                arm,
                float(alphas[arm]),
                int(root_seed),
                params=p,
                costs=cost,
                shipments=ships,
                n_burn=n_burn,
                n_score=n_score,
                lead_time=lead_time,
                run_id=f"m2-ladder-{arm}",
            )
        )

    profits["rollout"] = _evaluate_rollout_profit(
        float(alphas["rollout"]),
        int(root_seed),
        params=p,
        costs=cost,
        shipments=ships,
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
    )
    profits["dp"] = _evaluate_dp_profit()

    if out_dir is not None:
        artifact = Path(out_dir) / "m2_ladder_result.json"
    else:
        artifact = Path(DEFAULT_LADDER_RESULT_PATH)
    written = _write_ladder_artifact(
        artifact,
        profits=profits,
        alphas=alphas,
        root_seed=int(root_seed),
        production_backend=backend,
    )

    return LadderResult(
        points=LADDER_POINTS,
        profits=profits,
        production_backend=backend,
        artifact_paths=(written,),
        alphas=alphas,
        root_seed=int(root_seed),
    )
