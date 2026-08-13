"""Closed-loop Policy-driven episode driver (T-024).

Requires injectable ``shipments=`` — no Abdella filesystem default on this path.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.model import Cohort, DayStepResult, ModelParams, day_step
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule

from . import DayLog, EpisodeLog, LotState, generate_arrival_age

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from blueberries_voi.model.abdella import ShipmentTrace

# Match open-loop calendar epoch (sim/__init__.py).
_EPISODE_CALENDAR_EPOCH: date = date(2024, 1, 1)

__all__ = [
    "Policy",
    "case_round",
    "day_step",
    "run_closed_loop_episode",
]


@runtime_checkable
class Policy(Protocol):
    """CTL ordering surface: day + belief + pending pipeline → order qty."""

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int: ...


def _empty_shelf_belief() -> object:
    """Minimal ShelfBelief when closed-loop has not yet wired filter beliefs."""
    from blueberries_voi.filter.belief import ShelfBelief

    return ShelfBelief(
        lot_counts=[],
        age_marginals=[],
        tau_grid=[0.0, 2.0, 4.0, 6.0],
    )


def _invoke_policy_order(
    policy: Policy,
    day: int,
    belief: object | None,
    pending_orders: Mapping[int, int],
) -> int:
    """Dispatch day-first (T-024) or belief-first (T-028) policy surfaces."""
    sig = inspect.signature(policy.order)
    names = list(sig.parameters)
    if names and names[0] == "day":
        return int(policy.order(day, belief, pending_orders=pending_orders))
    shelf = belief if belief is not None else _empty_shelf_belief()
    kwargs: dict[str, object] = {"pending_orders": pending_orders}
    if "day" in sig.parameters:
        kwargs["day"] = day
    return int(policy.order(shelf, **kwargs))


def _shelf_belief_from_cohorts(cohorts: Sequence[Cohort]) -> object:
    """B-state ShelfBelief for CTL policies (ADR 0092 oracle path)."""
    from blueberries_voi.filter.belief import ShelfBelief, shelf_belief_from_oracle

    live = [c for c in cohorts if c.n > 0]
    if not live:
        return ShelfBelief(
            lot_counts=[],
            age_marginals=[],
            tau_grid=[0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0],
        )
    ages = [float(c.tau) for c in live]
    # Cover observed ages plus a small pad so Dirac knots stay on-grid.
    hi = max([*ages, 6.0]) + 2.0
    grid = [float(x) for x in range(0, int(hi) + 3, 2)]
    return shelf_belief_from_oracle(
        lot_counts=[int(c.n) for c in live],
        ages=ages,
        tau_grid=grid,
    )


def _call_day_step(
    cohorts: Sequence[Cohort],
    *,
    day: int,
    **kwargs: Any,
) -> DayStepResult:
    """ADR 0113 shim: forward ``day=`` only when ``day_step`` accepts it."""
    if "day" in inspect.signature(day_step).parameters:
        return day_step(cohorts, day=day, **kwargs)
    return day_step(cohorts, **kwargs)


def run_closed_loop_episode(
    policy: Policy,
    *,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams | None = None,
    root_seed: int = 0,
    run_id: str | int = "ep0",
    n_burn: int = 30,
    n_score: int = 90,
    lead_time: int = 1,
    spread_scale: float = 1.0,
    schedule: OrderSchedule | None = None,
) -> EpisodeLog:
    """Policy-driven forward sim sharing ``model.day_step`` and SIM-04 logs.

    ``shipments`` is required and must be non-empty. This path never loads
    Abdella parquet from the filesystem.

    Orders are gated by ``schedule`` (default ``DEFAULT_ORDER_SCHEDULE``): on
    non-order days the applied ``order_qty`` is 0 even if the policy asks
    nonzero. ``day_step`` still runs every calendar day.
    """
    if not shipments:
        msg = "shipments must be non-empty"
        raise ValueError(msg)

    p = params or ModelParams()
    sched = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
    ships = list(shipments)
    cohorts: list[Cohort] = []
    next_lot_id = 1
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score

    for day in range(horizon):
        # Snapshot pipeline before placing today's order (ADR 0092).
        pending_view: Mapping[int, int] = dict(pending)
        belief = _shelf_belief_from_cohorts(cohorts)
        raw_qty = _invoke_policy_order(policy, day, belief, pending_view)
        order_units = case_round(raw_qty, p.case_size)
        if not sched.can_order(day):
            order_units = 0
        pending[day + lead_time] = pending.get(day + lead_time, 0) + order_units

        arrival_units = int(pending.pop(day, 0))
        delivery: Cohort | None = None
        age_at_receipt: float | None = None
        pack_date: date | None = None
        if arrival_units > 0:
            rng_ship = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SHIP
            )
            rng_sensor = spawn_rng(
                root_seed, run_id=run_id, day=day, stream=STREAM_ARRIVAL_SENSOR
            )
            tau_in = generate_arrival_age(
                rng_ship, rng_sensor, ships, p, spread_scale=spread_scale
            )
            delivery = Cohort(n=arrival_units, tau=tau_in, lot_id=next_lot_id)
            next_lot_id += 1
            age_at_receipt = float(tau_in)
            receipt_day = _EPISODE_CALENDAR_EPOCH + timedelta(days=day)
            transit_days = max(round(age_at_receipt), 0)
            pack_date = receipt_day - timedelta(days=transit_days)

        pre_live_ids = [c.lot_id for c in cohorts if c.n > 0]
        rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
        result = _call_day_step(
            cohorts,
            day=day,
            params=p,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
        )
        cohorts = result.cohorts
        lots = [LotState(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts]
        sales_by_lot = {
            int(pre_live_ids[i]): int(result.sales_by_cohort[i])
            for i in range(len(pre_live_ids))
            if int(result.sales_by_cohort[i]) != 0
        }
        waste_by_lot = {
            int(pre_live_ids[i]): int(result.waste_by_cohort[i])
            for i in range(len(pre_live_ids))
            if int(result.waste_by_cohort[i]) != 0
        }
        log.days.append(
            DayLog(
                day=day,
                lots=lots,
                sales_total=result.sales_total,
                waste_total=result.waste_total,
                arrivals=arrival_units,
                order_qty=order_units,
                demand=result.demand,
                L=len(lots),
                sales_by_lot=sales_by_lot,
                waste_by_lot=waste_by_lot,
                age_at_receipt=age_at_receipt,
                pack_date=pack_date,
            )
        )
    return log
