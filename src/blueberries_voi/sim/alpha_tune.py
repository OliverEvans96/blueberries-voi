"""CTL-03 simulation-tuned alpha grid search (T-029).

Tuned alpha values are written under ``experiments/`` (default artifact path
``experiments/tuned_alpha.json`` -- see ``DEFAULT_TUNED_ALPHA_PATH``). This
module is the thin sim helper for alpha tuning; policies stay in ``controller/``
(no matplotlib / FS writers there). Experiment CLIs may live under
``experiments/``.

CI uses a reduced alpha grid (e.g. ``(0.7, 0.8, 0.9)``); desktop defaults are
recorded in the artifact ``header`` when saving (open question lock).

CAL-A3 / T-081: protection coverage is **day-indexed** under
``OrderSchedule`` (3/3/4 on Sun/Tue/Thu order days). Use
``protection_coverage_days`` / ``_protection_demand_quantile(..., protection_days=)``
so T-083 can retune alpha gates. Until T-084 / CAL-B4, coverage uses
**homogeneous μ** (i.i.d. daily NB) with day-varying length only;
heterogeneous / μ(day) is the B4 upgrade path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.filter.belief import ShelfBelief
from blueberries_voi.model import ModelParams
from blueberries_voi.sim.bakeoff_damped_sw import (
    DampedSurvivalWeightedPolicy,
    protection_demand_quantile,
)
from blueberries_voi.sim.bakeoff_ordering import ConstantOrderPolicy
from blueberries_voi.sim.bakeoff_rollout import RolloutPolicy
from blueberries_voi.sim.episode import run_closed_loop_episode
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.sim.profit import DEFAULT_PROFIT_COSTS, ProfitCosts, episode_profit
from blueberries_voi.sim.shipments import default_shipments

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from blueberries_voi.model.abdella import ShipmentTrace
    from blueberries_voi.sim.types_log import EpisodeLog

LADDER_ALPHA_ARMS: tuple[str, ...] = (
    "constant",
    "rung0",
    "sw",
    "rollout",
    "dp",
)
_PLACEHOLDER_ARMS: frozenset[str] = frozenset({"dp"})
_AVAILABLE_ARMS: frozenset[str] = frozenset({"constant", "rung0", "sw", "rollout"})

# Rollout budgets: CI-tiny defaults (m2 ladder / CrnBudgets parity).
DEFAULT_CI_ROLLOUT_H: int = 2
DEFAULT_CI_N_ROLLOUT_PATHS: int = 1
DEFAULT_CI_CANDIDATE_CASE_RADIUS: int = 1

DEFAULT_TUNED_ALPHA_PATH: str = "experiments/tuned_alpha.json"

# Tiny CI defaults; desktop grids belong in the artifact header.
DEFAULT_CI_ALPHAS: tuple[float, ...] = (0.7, 0.8, 0.9)
DEFAULT_DESKTOP_ALPHAS: tuple[float, ...] = (
    0.5,
    0.6,
    0.7,
    0.8,
    0.85,
    0.9,
    0.95,
)

_PROTECTION_DEMAND_DAYS: int = 2
_DEFAULT_RHO: float = 0.8


@dataclass(frozen=True)
class AlphaTuneEpisodeOutcomes:
    """Scored-episode aggregates for SIM-01=B alpha / rho tuning."""

    profit: float
    total_waste: int
    total_lost_sales: int


def _scored_outcomes(
    episode: EpisodeLog, costs: ProfitCosts
) -> AlphaTuneEpisodeOutcomes:
    waste = sum(day.waste_total for day in episode.scored)
    lost = sum(max(0, day.demand - day.sales_total) for day in episode.scored)
    return AlphaTuneEpisodeOutcomes(
        profit=float(episode_profit(episode, costs)),
        total_waste=int(waste),
        total_lost_sales=int(lost),
    )


__all__ = [
    "DEFAULT_CI_ALPHAS",
    "DEFAULT_CI_CANDIDATE_CASE_RADIUS",
    "DEFAULT_CI_N_ROLLOUT_PATHS",
    "DEFAULT_CI_ROLLOUT_H",
    "DEFAULT_DESKTOP_ALPHAS",
    "DEFAULT_TUNED_ALPHA_PATH",
    "LADDER_ALPHA_ARMS",
    "AlphaTuneEpisodeOutcomes",
    "assert_ladder_profit_claim_allowed",
    "evaluate_alpha_episode_outcomes",
    "evaluate_alpha_episode_profit",
    "load_tuned_alpha_table",
    "protection_coverage_days",
    "require_tuned_alpha_table",
    "save_tuned_alpha_table",
    "tune_alpha_grid",
]


def _empty_shelf_belief(_params: ModelParams) -> ShelfBelief:
    """Empty-shelf fallback when order() receives a non-ShelfBelief belief."""
    grid = [0.0, 2.0, 4.0, 6.0, 8.0]
    return ShelfBelief(lot_counts=[], f_marginals=[], f_grid=grid)


class _ClosedLoopPolicyAdapter:
    """Adapt controller policies to ``sim.episode.Policy`` call shape."""

    def __init__(
        self,
        arm_id: str,
        alpha: float,
        params: ModelParams,
        *,
        rho: float = _DEFAULT_RHO,
        schedule: OrderSchedule | None = None,
    ) -> None:
        self.arm_id = arm_id
        self.alpha = float(alpha)
        self.params = params
        self.schedule = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
        # Seed demand_target from a representative order-day protection length.
        seed_day = next(
            (d for d in range(7) if self.schedule.can_order(d)),
            0,
        )
        prot = int(self.schedule.protection_days(seed_day))
        d_star = _protection_demand_quantile(
            self.alpha, params, protection_days=prot, start_day=seed_day
        )
        if arm_id == "constant":
            # Constant order = case-rounded protection-interval fractile at alpha.
            self._inner: Any = ConstantOrderPolicy(
                round(d_star), case_size=int(params.case_size)
            )
            self._kind = "constant"
        elif arm_id == "rung0":
            self._inner = CorrectedAgeBlindPolicy(
                alpha=self.alpha,
                params=params,
                demand_target=d_star,
                case_size=int(params.case_size),
                schedule=self.schedule,
            )
            self._kind = "rung0"
        elif arm_id == "sw":
            self._inner = DampedSurvivalWeightedPolicy(
                rho=float(rho),
                alpha=self.alpha,
                params=params,
                schedule=self.schedule,
            )
            self._kind = "sw"
        else:
            msg = f"no closed-loop adapter for arm {arm_id!r}"
            raise ValueError(msg)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        pending = pending_orders if pending_orders is not None else {}
        if self._kind == "constant":
            return int(self._inner.order(belief, day=day, pending_orders=()))
        if self._kind == "rung0":
            return int(self._inner.order(day, belief, pending_orders=pending))
        shelf = (
            belief
            if isinstance(belief, ShelfBelief)
            else _empty_shelf_belief(self.params)
        )
        return int(self._inner.order(shelf, day=day, pending_orders=pending))


def protection_coverage_days(day: int, *, schedule: OrderSchedule | None = None) -> int:
    """Day-indexed protection length for alpha retune (T-083 / CAL-A3).

    Under the default MWF ``OrderSchedule``, Sun/Tue/Thu order days cover
    3 / 3 / 4 homogeneous-μ demand days (ADR 0114).
    """
    sched = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
    return int(sched.protection_days(day))


def _protection_demand_quantile(
    alpha: float,
    params: ModelParams,
    *,
    protection_days: int | None = None,
    start_day: int = 0,
) -> float:
    """Alpha-quantile of protection-window NB demand."""
    n_days = (
        _PROTECTION_DEMAND_DAYS if protection_days is None else int(protection_days)
    )
    return protection_demand_quantile(
        alpha, params, protection_days=n_days, start_day=start_day
    )


def _shipments_wire(
    ships: Sequence[ShipmentTrace],
) -> tuple[list[list[float]], list[list[float]]]:
    times = [list(map(float, s.times_d)) for s in ships]
    temps = [list(map(float, s.temps_c)) for s in ships]
    return times, temps


def _evaluate_via_rust_kernel(
    arm_id: str,
    alpha: float,
    rho: float,
    root_seed: int,
    ships: Sequence[ShipmentTrace],
    *,
    params: ModelParams,
    n_burn: int,
    n_score: int,
    lead_time: int,
    costs: ProfitCosts,
    rollout_h: int,
    n_rollout_paths: int,
    candidate_case_radius: int,
) -> AlphaTuneEpisodeOutcomes | None:
    """Return scored outcomes from ``voi_core`` when the PyO3 shim is available."""
    if params.demand_profile is not None:
        return None
    if not rust_available() or rust_core is None:
        return None
    fn = getattr(rust_core, "evaluate_alpha_tune_outcomes_py", None)
    if fn is None:
        return None
    times, temps = _shipments_wire(ships)
    profit, waste, lost = fn(
        arm_id,
        float(alpha),
        int(root_seed),
        n_burn=int(n_burn),
        n_score=int(n_score),
        lead_time=int(lead_time),
        rho=float(rho),
        unit_margin=float(costs.unit_margin),
        waste_cost=float(costs.waste_cost),
        stockout_penalty=float(costs.stockout_penalty),
        rollout_h=int(rollout_h),
        n_rollout_paths=int(n_rollout_paths),
        candidate_case_radius=int(candidate_case_radius),
        times=times,
        temps=temps,
    )
    return AlphaTuneEpisodeOutcomes(
        profit=float(profit),
        total_waste=int(waste),
        total_lost_sales=int(lost),
    )


def _evaluate_rollout_python(
    alpha: float,
    rho: float,
    root_seed: int,
    ships: Sequence[ShipmentTrace],
    *,
    params: ModelParams,
    costs: ProfitCosts,
    n_burn: int,
    n_score: int,
    lead_time: int,
    run_id: str | int,
    rollout_h: int,
    n_rollout_paths: int,
    candidate_case_radius: int,
) -> AlphaTuneEpisodeOutcomes:
    """Python fallback: damped-SW base + one-step rollout (m2 ladder pattern)."""
    base = DampedSurvivalWeightedPolicy(
        rho=float(rho),
        alpha=float(alpha),
        params=params,
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    policy = RolloutPolicy(
        base_policy=base,
        params=params,
        root_seed=int(root_seed),
        run_id=str(run_id),
        H=int(rollout_h),
        n_rollout_paths=int(n_rollout_paths),
        candidate_case_radius=int(candidate_case_radius),
        lead_time=int(lead_time),
    )
    episode = run_closed_loop_episode(
        policy,
        shipments=list(ships),
        params=params,
        root_seed=int(root_seed),
        run_id=run_id,
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    return _scored_outcomes(episode, costs)


def _evaluate_python_episode(
    arm_id: str,
    alpha: float,
    rho: float,
    root_seed: int,
    ships: Sequence[ShipmentTrace],
    *,
    params: ModelParams,
    costs: ProfitCosts,
    n_burn: int,
    n_score: int,
    lead_time: int,
    run_id: str | int,
) -> AlphaTuneEpisodeOutcomes:
    policy = _ClosedLoopPolicyAdapter(arm_id, alpha, params, rho=rho)
    episode = run_closed_loop_episode(
        policy,
        shipments=ships,
        params=params,
        root_seed=int(root_seed),
        run_id=run_id,
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
        schedule=DEFAULT_ORDER_SCHEDULE,
    )
    return _scored_outcomes(episode, costs)


def evaluate_alpha_episode_outcomes(
    arm_id: str,
    alpha: float,
    root_seed: int,
    *,
    rho: float = _DEFAULT_RHO,
    params: ModelParams | None = None,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    n_burn: int = 2,
    n_score: int = 5,
    lead_time: int = 1,
    run_id: str | int = "alpha-tune",
    rollout_h: int = DEFAULT_CI_ROLLOUT_H,
    n_rollout_paths: int = DEFAULT_CI_N_ROLLOUT_PATHS,
    candidate_case_radius: int = DEFAULT_CI_CANDIDATE_CASE_RADIUS,
) -> AlphaTuneEpisodeOutcomes:
    """Score one (arm, alpha, rho) via closed-loop episode aggregates (SIM-01=B)."""
    p = params or ModelParams()
    ships = list(shipments) if shipments is not None else default_shipments()
    use_costs = costs if costs is not None else DEFAULT_PROFIT_COSTS
    rust_outcomes = _evaluate_via_rust_kernel(
        arm_id,
        alpha,
        rho,
        int(root_seed),
        ships,
        params=p,
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
        costs=use_costs,
        rollout_h=rollout_h,
        n_rollout_paths=n_rollout_paths,
        candidate_case_radius=candidate_case_radius,
    )
    if rust_outcomes is not None:
        return rust_outcomes

    if arm_id == "rollout":
        return _evaluate_rollout_python(
            alpha,
            rho,
            int(root_seed),
            ships,
            params=p,
            costs=use_costs,
            n_burn=n_burn,
            n_score=n_score,
            lead_time=lead_time,
            run_id=run_id,
            rollout_h=rollout_h,
            n_rollout_paths=n_rollout_paths,
            candidate_case_radius=candidate_case_radius,
        )

    return _evaluate_python_episode(
        arm_id,
        alpha,
        rho,
        int(root_seed),
        ships,
        params=p,
        costs=use_costs,
        n_burn=n_burn,
        n_score=n_score,
        lead_time=lead_time,
        run_id=run_id,
    )


def evaluate_alpha_episode_profit(
    arm_id: str,
    alpha: float,
    root_seed: int,
    *,
    rho: float = _DEFAULT_RHO,
    params: ModelParams | None = None,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    n_burn: int = 2,
    n_score: int = 5,
    lead_time: int = 1,
    run_id: str | int = "alpha-tune",
    rollout_h: int = DEFAULT_CI_ROLLOUT_H,
    n_rollout_paths: int = DEFAULT_CI_N_ROLLOUT_PATHS,
    candidate_case_radius: int = DEFAULT_CI_CANDIDATE_CASE_RADIUS,
) -> float:
    """Score one (arm, alpha) pair via closed-loop ``episode_profit`` (SIM-01=B)."""
    return float(
        evaluate_alpha_episode_outcomes(
            arm_id,
            alpha,
            root_seed,
            rho=rho,
            params=params,
            costs=costs,
            shipments=shipments,
            n_burn=n_burn,
            n_score=n_score,
            lead_time=lead_time,
            run_id=run_id,
            rollout_h=rollout_h,
            n_rollout_paths=n_rollout_paths,
            candidate_case_radius=candidate_case_radius,
        ).profit
    )


def tune_alpha_grid(
    arm_id: str,
    *,
    alphas: Sequence[float],
    root_seed: int,
    params: ModelParams | None = None,
    costs: ProfitCosts | None = None,
    shipments: Sequence[ShipmentTrace] | None = None,
    n_burn: int = 2,
    n_score: int = 5,
    rollout_h: int = DEFAULT_CI_ROLLOUT_H,
    n_rollout_paths: int = DEFAULT_CI_N_ROLLOUT_PATHS,
    candidate_case_radius: int = DEFAULT_CI_CANDIDATE_CASE_RADIUS,
) -> float:
    """Grid-search alpha for one ladder arm under shared CRN ``root_seed``.

    Returns the alpha in ``alphas`` with highest ``episode_profit``. Placeholder
    arm ``dp`` raises until T-031 lands.
    """
    if arm_id not in LADDER_ALPHA_ARMS:
        msg = f"unknown ladder arm {arm_id!r}; expected one of {LADDER_ALPHA_ARMS}"
        raise ValueError(msg)
    if arm_id in _PLACEHOLDER_ARMS:
        msg = (
            f"{arm_id} is a placeholder arm (unavailable until T-031); "
            "alpha tuning is not implemented yet"
        )
        raise NotImplementedError(msg)
    if arm_id not in _AVAILABLE_ARMS:
        msg = f"arm {arm_id!r} is registered but not available for tuning"
        raise ValueError(msg)
    if len(alphas) == 0:
        msg = "alphas must be a non-empty sequence"
        raise ValueError(msg)

    best_alpha = float(alphas[0])
    best_profit = float("-inf")
    for alpha in alphas:
        profit = evaluate_alpha_episode_profit(
            arm_id,
            float(alpha),
            int(root_seed),
            params=params,
            costs=costs,
            shipments=shipments,
            n_burn=n_burn,
            n_score=n_score,
            rollout_h=rollout_h,
            n_rollout_paths=n_rollout_paths,
            candidate_case_radius=candidate_case_radius,
        )
        if profit > best_profit:
            best_profit = profit
            best_alpha = float(alpha)
    return best_alpha


def save_tuned_alpha_table(
    path: str | Path,
    table: Mapping[str, float],
    *,
    header: Mapping[str, Any] | None = None,
) -> None:
    """Write tuned alpha table to ``path`` (``.json`` or ``.md``)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    alphas = {str(k): float(v) for k, v in table.items()}
    if out.suffix.lower() == ".md":
        lines = ["# Tuned alpha table\n", "\n"]
        if header is not None:
            lines.append("## Header (CI vs desktop defaults)\n")
            lines.append("\n")
            for key, value in header.items():
                lines.append(f"- {key}: {value}\n")
            lines.append("\n")
        lines.append("## Alphas\n")
        lines.append("\n")
        for arm, alpha in alphas.items():
            lines.append(f"- {arm}: {alpha}\n")
        out.write_text("".join(lines), encoding="utf-8")
        return

    payload: dict[str, Any] = {"alphas": alphas}
    if header is not None:
        payload["header"] = dict(header)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_tuned_alpha_table(path: str | Path) -> dict[str, float]:
    """Load arm -> alpha mapping from a JSON or markdown artifact."""
    src = Path(path)
    text = src.read_text(encoding="utf-8")
    if src.suffix.lower() == ".md":
        return _parse_md_alpha_table(text)
    data = json.loads(text)
    if isinstance(data, dict) and "alphas" in data:
        raw = data["alphas"]
    else:
        raw = {k: v for k, v in data.items() if k != "header"}
    if not isinstance(raw, dict):
        msg = f"tuned alpha artifact must map arms to floats, got {type(raw)!r}"
        raise ValueError(msg)
    return {str(k): float(v) for k, v in raw.items()}


def _parse_md_alpha_table(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    in_alphas = False
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## alphas"):
            in_alphas = True
            continue
        if stripped.startswith("## ") and in_alphas:
            break
        if not in_alphas:
            continue
        if line.strip().startswith("- "):
            body = line.strip()[2:]
            if ":" not in body:
                continue
            arm, _, rest = body.partition(":")
            result[arm.strip()] = float(rest.strip())
    return result


def require_tuned_alpha_table(path: str | Path) -> dict[str, float]:
    """Load a tuned alpha table or fail if the artifact is missing."""
    src = Path(path)
    if not src.is_file():
        msg = f"tuned alpha table not found: {src}"
        raise FileNotFoundError(msg)
    return load_tuned_alpha_table(src)


def assert_ladder_profit_claim_allowed(path: str | Path) -> None:
    """Hard gate: ladder profit claims require a complete tuned alpha table."""
    table = require_tuned_alpha_table(path)
    missing = [arm for arm in LADDER_ALPHA_ARMS if arm not in table]
    if missing:
        msg = (
            "ladder profit claim rejected: tuned alpha table incomplete; "
            f"missing arms {missing}"
        )
        raise ValueError(msg)
    for arm in LADDER_ALPHA_ARMS:
        float(table[arm])
