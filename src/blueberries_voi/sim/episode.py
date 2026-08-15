"""Closed-loop Policy-driven episode driver (T-024).

Requires injectable ``shipments=`` — no Abdella filesystem default on this path.

Burn-in under CAL-01 acknowledges **periodic** age under the MWF
``OrderSchedule`` (orders Sun/Tue/Thu), not a daily-stationary age mix alone.
Default ``n_burn`` is a multiple of 7 so scored episodes start on a weekly
boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from blueberries_voi.model import Cohort, ModelParams
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim.case_round import case_round
from blueberries_voi.sim.day_tick import (
    enqueue_pending_order,
    lot_states_from_cohorts,
    nonzero_lot_maps,
    pack_date_from_epoch,
    pop_arrival_units,
    pre_live_lot_ids,
)
from blueberries_voi.sim.open_loop import generate_arrival_age
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.sim.rust_bridge import day_step
from blueberries_voi.sim.types_log import DayLog, EpisodeLog

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from blueberries_voi.model.abdella import ShipmentTrace

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


_EMPTY_ORACLE_TAU_GRID: tuple[float, ...] = (
    0.0,
    2.0,
    4.0,
    6.0,
    8.0,
    10.0,
    12.0,
    14.0,
)


def _shelf_belief_from_cohorts(cohorts: Sequence[Cohort]) -> object:
    """B-state ShelfBelief for CTL policies (ADR 0092 oracle path)."""
    from blueberries_voi.filter.belief import shelf_belief_from_cohorts_oracle

    return shelf_belief_from_cohorts_oracle(
        cohorts, empty_tau_grid=_EMPTY_ORACLE_TAU_GRID
    )


def _invoke_order(
    policy: Policy,
    day: int,
    belief: object,
    pending_orders: Mapping[int, int],
) -> int:
    """Dispatch ``Policy.order`` (day-first CTL surface)."""
    return int(
        policy.order(
            day,
            belief,
            pending_orders=pending_orders,
        )
    )


def run_closed_loop_episode(
    policy: Policy,
    *,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams | None = None,
    root_seed: int = 0,
    run_id: str | int = "ep0",
    n_burn: int = 28,
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

    Default ``n_burn=28`` (four weeks) aligns burn-in with periodic MWF age
    rather than a daily-stationary 30-day window.
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
        raw_qty = _invoke_order(policy, day, belief, pending_view)
        # Nearest case rounding (not ceil): intentional fork vs open-loop/day_driver.
        order_units = case_round(raw_qty, p.case_size)
        if not sched.can_order(day):
            order_units = 0
        enqueue_pending_order(pending, day, lead_time, order_units)

        arrival_units = pop_arrival_units(pending, day)
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
            pack_date = pack_date_from_epoch(day, age_at_receipt)

        pre_live_ids = pre_live_lot_ids(cohorts)
        rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
        result = day_step(
            cohorts,
            day=day,
            params=p,
            delivery=delivery,
            rng_demand=rng_d,
            rng_alloc=rng_a,
            rng_spoil=rng_s,
        )
        cohorts = result.cohorts
        sales_by_lot, waste_by_lot = nonzero_lot_maps(
            pre_live_ids, result.sales_by_cohort, result.waste_by_cohort
        )
        log.days.append(
            DayLog(
                day=day,
                lots=lot_states_from_cohorts(cohorts),
                sales_total=result.sales_total,
                waste_total=result.waste_total,
                arrivals=arrival_units,
                order_qty=order_units,
                demand=result.demand,
                L=len(cohorts),
                sales_by_lot=sales_by_lot,
                waste_by_lot=waste_by_lot,
                age_at_receipt=age_at_receipt,
                pack_date=pack_date,
            )
        )
    return log
