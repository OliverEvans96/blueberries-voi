"""CTL-02/04 one-step rollout with survival-weighted terminal salvage.

ADR 0059 (CTL-02=B): single-step policy improvement over a base policy.
ADR 0061 (CTL-04=B): horizon H ~ 2x shelf life with terminal salvage

    V_T = m * sum_l w_long(tau_l) * n_l

where ``w_long`` is computed from queue position under oldest-first allocation
(exported as ``w_long_oldest_first``). Forward sims call shared ``model.day_step``
(no shadow dynamics). Rollouts are sequential only (single-threaded paths).

ADR 0112 / T-083: production rollout horizon presets step in **multiples of 7**
calendar days so weekly / MWF periodicity is preserved (H ∈ {7, 14, 21, 28, …}).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from blueberries_voi import model as model_pkg
from blueberries_voi.filter.belief import ShelfBelief, empty_shelf_belief
from blueberries_voi.model import Cohort, ModelParams, weibull_survival
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL, spawn_rng
from blueberries_voi.sim.profit import ProfitCosts, day_profit
from blueberries_voi.sim.rust_bridge import day_step as day_step
from blueberries_voi.sim.types_log import DayLog

# Production presets: multiples of 7 (weekly MWF cadence; ADR 0112 re-derive #3).
DEFAULT_ROLLOUT_HORIZONS: tuple[int, ...] = (7, 14, 21, 28)
# CTL-04=B desktop default: H = 2 * eta_ref (ModelParams.eta_ref=14 → 28).
DEFAULT_ROLLOUT_H: int = 28
DEFAULT_N_ROLLOUT_PATHS: int = 8
DEFAULT_CANDIDATE_CASE_RADIUS: int = 2
DEFAULT_N_PARTICLES: int = 64
DEFAULT_LEAD_TIME: int = 1
_DEFAULT_MARGIN: float = 2.0
_DEFAULT_WASTE_COST: float = 1.5
_DEFAULT_STOCKOUT_PENALTY: float = 3.0
_EMPTY_TAU_GRID: tuple[float, ...] = (0.0, 2.0, 4.0, 6.0)


class _BaseOrderPolicy(Protocol):
    def order(
        self,
        belief: ShelfBelief,
        *,
        day: int = 0,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int: ...


@dataclass(frozen=True)
class CrnDesyncResult:
    """ENG-04 CRN desync detector outcome."""

    ok: bool
    status: str


def detect_crn_desync(
    *,
    address_a: Mapping[str, Any],
    address_b: Mapping[str, Any],
    n_draws: int = 32,
) -> CrnDesyncResult:
    """Compare two SIM-05 stream addresses; ``ok`` iff draw sequences match."""
    if n_draws <= 0:
        msg = f"n_draws must be positive, got {n_draws}"
        raise ValueError(msg)
    a = spawn_rng(
        int(address_a["root_seed"]),
        run_id=address_a["run_id"],
        day=int(address_a["day"]),
        stream=str(address_a["stream"]),
    )
    b = spawn_rng(
        int(address_b["root_seed"]),
        run_id=address_b["run_id"],
        day=int(address_b["day"]),
        stream=str(address_b["stream"]),
    )
    draws_a = a.random(int(n_draws))
    draws_b = b.random(int(n_draws))
    if np.array_equal(draws_a, draws_b):
        return CrnDesyncResult(ok=True, status="ok")
    return CrnDesyncResult(ok=False, status="desync")


def _lot_n(lot: Any) -> float:
    if isinstance(lot, Mapping):
        return float(lot["n"])
    return float(lot.n)


def _lot_tau(lot: Any) -> float:
    if isinstance(lot, Mapping):
        return float(lot["tau"])
    return float(lot.tau)


def w_long_oldest_first(
    lots: Sequence[Mapping[str, Any]] | Sequence[Any],
    *,
    params: ModelParams,
) -> list[float]:
    """Survival weights for lots in oldest-first queue order (ADR 0061).

    Lots are interpreted in the given order as the oldest-first allocation
    queue. ``w_long(τ)`` is Weibull survival at the lot's effective age so
    newer / fresher stock (higher S) contributes more salvage value.
    """
    weights: list[float] = []
    for lot in lots:
        tau = float(_lot_tau(lot))
        weights.append(weibull_survival(tau, beta=params.beta, eta=params.eta_ref))
    return weights


def terminal_salvage_value(
    lots: Sequence[Mapping[str, Any]] | Sequence[Any],
    *,
    margin: float,
    params: ModelParams,
) -> float:
    """Terminal salvage V_T = m * sum_l w_long(tau_l) * n_l (ADR 0061 / CTL-04)."""
    if not lots:
        return 0.0
    weights = w_long_oldest_first(lots, params=params)
    total = 0.0
    for w, lot in zip(weights, lots, strict=True):
        total += float(w) * float(_lot_n(lot))
    return float(margin) * total


def _cohorts_from_belief(belief: ShelfBelief) -> list[Cohort]:
    cohorts: list[Cohort] = []
    grid = [float(t) for t in belief.tau_grid]
    for i, (n_raw, marg) in enumerate(
        zip(belief.lot_counts, belief.age_marginals, strict=True)
    ):
        n = round(float(n_raw))
        if n <= 0:
            continue
        if grid and marg:
            tau = float(
                sum(float(p) * float(t) for p, t in zip(marg, grid, strict=True))
            )
        else:
            tau = 0.0
        cohorts.append(Cohort(n=n, tau=tau, lot_id=i + 1))
    return cohorts


def _belief_from_cohorts(
    cohorts: Sequence[Cohort],
    *,
    tau_grid: Sequence[float],
) -> ShelfBelief:
    """Rebuild ShelfBelief after a rollout day_step using the parent τ grid."""
    from blueberries_voi.filter.belief import shelf_belief_from_oracle

    grid = list(tau_grid) if tau_grid else list(_EMPTY_TAU_GRID)
    live = [c for c in cohorts if c.n > 0]
    if not live:
        return empty_shelf_belief(tau_grid=grid)
    return shelf_belief_from_oracle(
        lot_counts=[c.n for c in live],
        ages=[c.tau for c in live],
        tau_grid=grid,
    )


def _lots_for_salvage(cohorts: Sequence[Cohort]) -> list[dict[str, float]]:
    # Oldest-first queue: higher tau first.
    ordered = sorted(
        (c for c in cohorts if c.n > 0),
        key=lambda c: float(c.tau),
        reverse=True,
    )
    return [{"n": float(c.n), "tau": float(c.tau)} for c in ordered]


def _day_profit(
    *,
    sales: int,
    waste: int,
    demand: int,
    margin: float,
    waste_cost: float,
    stockout_penalty: float,
) -> float:
    """Thin wrapper over ``sim.profit.day_profit`` (same SIM-01=B formula)."""
    day = DayLog(
        day=0,
        lots=[],
        sales_total=int(sales),
        waste_total=int(waste),
        arrivals=0,
        order_qty=0,
        demand=int(demand),
        L=0,
    )
    costs = ProfitCosts(
        unit_margin=float(margin),
        waste_cost=float(waste_cost),
        stockout_penalty=float(stockout_penalty),
    )
    return float(day_profit(day, costs))


def _mean_candidate_value(
    belief: ShelfBelief,
    *,
    first_order: int,
    base_policy: _BaseOrderPolicy,
    params: ModelParams,
    root_seed: int,
    run_id: str | int,
    day0: int,
    H: int,
    n_paths: int,
    pending0: Mapping[int, int],
    lead_time: int,
    margin: float,
    waste_cost: float,
    stockout_penalty: float,
) -> float:
    total = 0.0
    for path in range(n_paths):
        total += _path_value(
            belief,
            first_order=first_order,
            base_policy=base_policy,
            params=params,
            root_seed=root_seed,
            run_id=run_id,
            path=path,
            day0=day0,
            H=H,
            pending0=pending0,
            lead_time=lead_time,
            margin=margin,
            waste_cost=waste_cost,
            stockout_penalty=stockout_penalty,
        )
    return total / float(n_paths)


def _path_value(
    belief: ShelfBelief,
    *,
    first_order: int,
    base_policy: _BaseOrderPolicy,
    params: ModelParams,
    root_seed: int,
    run_id: str | int,
    path: int,
    day0: int,
    H: int,
    pending0: Mapping[int, int],
    lead_time: int,
    margin: float,
    waste_cost: float,
    stockout_penalty: float,
) -> float:
    # Path id in run_id keeps CRN paired across candidates (same path/day streams).
    path_run = f"{run_id}|rollout|p{path}"
    cohorts = _cohorts_from_belief(belief)
    pending = {int(k): int(v) for k, v in pending0.items()}
    shelf = belief
    next_lot_id = max((c.lot_id for c in cohorts), default=0) + 1
    value = 0.0

    for h in range(H):
        sim_day = day0 + h
        pending_view = dict(pending)
        if h == 0:
            order_qty = int(first_order)
        else:
            order_qty = int(
                base_policy.order(shelf, day=sim_day, pending_orders=pending_view)
            )
        pending[sim_day + lead_time] = pending.get(sim_day + lead_time, 0) + max(
            0, order_qty
        )

        arrival_units = int(pending.pop(sim_day, 0))
        delivery: Cohort | None = None
        if arrival_units > 0:
            delivery = Cohort(n=arrival_units, tau=0.0, lot_id=next_lot_id)
            next_lot_id += 1

        rng_d = spawn_rng(root_seed, run_id=path_run, day=sim_day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=path_run, day=sim_day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=path_run, day=sim_day, stream=STREAM_SPOIL)
        # Lookup via model package so monkeypatched ``model.day_step`` is seen.
        result = model_pkg.day_step(
            cohorts,
            params=params,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
        )
        cohorts = result.cohorts
        value += _day_profit(
            sales=result.sales_total,
            waste=result.waste_total,
            demand=result.demand,
            margin=margin,
            waste_cost=waste_cost,
            stockout_penalty=stockout_penalty,
        )
        shelf = _belief_from_cohorts(cohorts, tau_grid=belief.tau_grid)

    value += terminal_salvage_value(
        _lots_for_salvage(cohorts),
        margin=margin,
        params=params,
    )
    return value


def candidate_orders(
    base_q: int,
    *,
    case_size: int,
    radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
) -> list[int]:
    """Case multiples within ±``radius`` cases of ``base_q`` (non-negative)."""
    if case_size <= 0:
        msg = f"case_size must be positive, got {case_size}"
        raise ValueError(msg)
    if radius < 0:
        msg = f"radius must be non-negative, got {radius}"
        raise ValueError(msg)
    base_cases = int(base_q) // int(case_size)
    out: list[int] = []
    for dc in range(-int(radius), int(radius) + 1):
        q = (base_cases + dc) * int(case_size)
        if q >= 0:
            out.append(q)
    if not out:
        msg = "candidate neighbourhood is empty"
        raise ValueError(msg)
    return out


def rollout_order(
    belief: ShelfBelief,
    *,
    base_policy: _BaseOrderPolicy,
    params: ModelParams,
    rng_address: Mapping[str, Any],
    H: int = DEFAULT_ROLLOUT_H,
    n_rollout_paths: int = DEFAULT_N_ROLLOUT_PATHS,
    candidate_case_radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
    n_particles: int = DEFAULT_N_PARTICLES,
    candidates: Sequence[int] | None = None,
    pending_orders: Mapping[int, int] | None = None,
    day: int = 0,
    lead_time: int = DEFAULT_LEAD_TIME,
    margin: float = _DEFAULT_MARGIN,
    waste_cost: float = _DEFAULT_WASTE_COST,
    stockout_penalty: float = _DEFAULT_STOCKOUT_PENALTY,
) -> int:
    """One-step rollout: pick the case order with highest CRN-paired path value.

    Evaluates a neighbourhood of candidates around the base policy order for
    one improvement step. Each candidate is scored by ``n_rollout_paths``
    sequential forward sims of horizon ``H`` using shared ``day_step``, then
    terminal salvage ``V_T = m * sum_l w_long(tau_l) * n_l``.

    ``n_particles`` is reserved as a desktop compute-budget knob (sample / MF
    cap); the current mean-field rollout path does not resample particles.
    """
    del n_particles  # budget surface; MF rollout does not consume particles yet
    if int(H) <= 0:
        msg = f"H must be positive, got {H}"
        raise ValueError(msg)
    if int(n_rollout_paths) <= 0:
        msg = f"n_rollout_paths must be positive, got {n_rollout_paths}"
        raise ValueError(msg)

    pending0: dict[int, int] = (
        {int(k): int(v) for k, v in pending_orders.items()}
        if pending_orders is not None
        else {}
    )
    base_q = int(base_policy.order(belief, day=int(day), pending_orders=dict(pending0)))
    if candidates is None:
        cand_list = candidate_orders(
            base_q,
            case_size=int(params.case_size),
            radius=int(candidate_case_radius),
        )
    else:
        cand_list = [int(q) for q in candidates]
    if not cand_list:
        msg = "candidates must be non-empty"
        raise ValueError(msg)

    # Prefer base on ties: score base first, only switch on strict improvement.
    ordered = [base_q] + [q for q in cand_list if q != base_q]
    # Deduplicate while preserving order
    seen: set[int] = set()
    unique: list[int] = []
    for q in ordered:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    root_seed = int(rng_address["root_seed"])
    run_id = rng_address["run_id"]
    best_q = unique[0]
    best_score = float("-inf")
    for q in unique:
        score = _mean_candidate_value(
            belief,
            first_order=q,
            base_policy=base_policy,
            params=params,
            root_seed=root_seed,
            run_id=run_id,
            day0=int(day),
            H=int(H),
            n_paths=int(n_rollout_paths),
            pending0=pending0,
            lead_time=int(lead_time),
            margin=float(margin),
            waste_cost=float(waste_cost),
            stockout_penalty=float(stockout_penalty),
        )
        if score > best_score:
            best_score = score
            best_q = q
    return int(best_q)


class RolloutPolicy:
    """Closed-loop wrapper: day-first Protocol calling ``rollout_order``."""

    def __init__(
        self,
        *,
        base_policy: _BaseOrderPolicy,
        params: ModelParams,
        root_seed: int = 0,
        run_id: str = "rollout",
        H: int = DEFAULT_ROLLOUT_H,
        n_rollout_paths: int = DEFAULT_N_ROLLOUT_PATHS,
        candidate_case_radius: int = DEFAULT_CANDIDATE_CASE_RADIUS,
        n_particles: int = DEFAULT_N_PARTICLES,
        lead_time: int = DEFAULT_LEAD_TIME,
    ) -> None:
        self.base_policy = base_policy
        self.params = params
        self.root_seed = int(root_seed)
        self.run_id = run_id
        self.H = int(H)
        self.n_rollout_paths = int(n_rollout_paths)
        self.candidate_case_radius = int(candidate_case_radius)
        self.n_particles = int(n_particles)
        self.lead_time = int(lead_time)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        shelf = (
            belief
            if isinstance(belief, ShelfBelief)
            else empty_shelf_belief(tau_grid=_EMPTY_TAU_GRID)
        )
        pending = {} if pending_orders is None else pending_orders
        # Without on-hand lots, closed-loop currently has no shelf signal; matching
        # the base order preserves the CTL-02 improvement guarantee (tie).
        if not any(float(n) > 0.0 for n in shelf.lot_counts):
            return int(
                self.base_policy.order(shelf, day=int(day), pending_orders=pending)
            )
        return rollout_order(
            shelf,
            base_policy=self.base_policy,
            params=self.params,
            rng_address={
                "root_seed": self.root_seed,
                "run_id": f"{self.run_id}-d{int(day)}",
            },
            H=self.H,
            n_rollout_paths=self.n_rollout_paths,
            candidate_case_radius=self.candidate_case_radius,
            n_particles=self.n_particles,
            pending_orders=pending,
            day=int(day),
            lead_time=self.lead_time,
        )


__all__ = [
    "DEFAULT_CANDIDATE_CASE_RADIUS",
    "DEFAULT_N_PARTICLES",
    "DEFAULT_N_ROLLOUT_PATHS",
    "DEFAULT_ROLLOUT_H",
    "DEFAULT_ROLLOUT_HORIZONS",
    "CrnDesyncResult",
    "RolloutPolicy",
    "candidate_orders",
    "day_step",
    "detect_crn_desync",
    "rollout_order",
    "terminal_salvage_value",
    "w_long_oldest_first",
]
