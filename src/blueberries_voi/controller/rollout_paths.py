"""Rollout path / belief helpers (peeled from controller.rollout)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from blueberries_voi import model as model_pkg
from blueberries_voi.controller.salvage import terminal_salvage_value
from blueberries_voi.filter.belief import ShelfBelief, empty_shelf_belief
from blueberries_voi.model import Cohort, ModelParams
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL, spawn_rng
from blueberries_voi.sim.profit import ProfitCosts, day_profit
from blueberries_voi.sim.types_log import DayLog

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_EMPTY_TAU_GRID: tuple[float, ...] = (0.0, 2.0, 4.0, 6.0)


class _BaseOrderPolicy(Protocol):
    def order(
        self,
        belief: ShelfBelief,
        *,
        day: int = 0,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int: ...


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
