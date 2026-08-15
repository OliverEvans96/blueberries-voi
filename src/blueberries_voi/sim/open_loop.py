"""Open-loop forward simulator, arrival generator, and base-stock order helper."""

from __future__ import annotations

import numpy as np

from blueberries_voi.model import Cohort, ModelParams
from blueberries_voi.sim.rust_bridge import day_step
from blueberries_voi.model.abdella import (
    ShipmentTrace,
    load_abdella_shipments,
    shipment_arrival_age,
)
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim.day_tick import (
    enqueue_pending_order,
    lot_states_from_cohorts,
    nonzero_lot_maps,
    pack_date_from_epoch,
    pop_arrival_units,
    pre_live_lot_ids,
)
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.sim.types_log import DayLog, EpisodeLog

__all__ = [
    "generate_arrival_age",
    "open_loop_order",
    "run_episode",
]


def generate_arrival_age(
    rng_ship: np.random.Generator,
    rng_sensor: np.random.Generator,
    shipments: list[ShipmentTrace],
    params: ModelParams,
    *,
    spread_scale: float = 1.0,
) -> float:
    """Bootstrap a shipment, integrate Arrhenius age, optionally tighten spread.

    ``spread_scale`` < 1 shrinks ages toward the mean (FIL-11 Stage A contrast)
    without forking a second code path.
    """
    if not shipments:
        msg = "shipments must be non-empty"
        raise ValueError(msg)
    idx = int(rng_ship.integers(0, len(shipments)))
    # Sensor stream reserved for future within-shipment sensor draws; consume a
    # uniform to keep slot addressing stable even when unused.
    _ = float(rng_sensor.random())
    ship = shipments[idx]
    age = shipment_arrival_age(ship, q10=params.q10, t_ref_c=params.t_ref_c)
    ages = [
        shipment_arrival_age(s, q10=params.q10, t_ref_c=params.t_ref_c)
        for s in shipments
    ]
    mean_age = float(np.mean(ages))
    return float(mean_age + spread_scale * (age - mean_age))


def open_loop_order(on_hand: int, *, S: int = 60) -> int:
    """Age-blind base-stock order quantity (M1 driver only; not CTL baseline)."""
    return max(0, int(S) - int(on_hand))


def run_episode(
    params: ModelParams | None = None,
    *,
    root_seed: int = 0,
    run_id: str | int = "ep0",
    n_burn: int = 28,
    n_score: int = 90,
    S: int = 60,
    lead_time: int = 1,
    spread_scale: float = 1.0,
    shipments: list[ShipmentTrace] | None = None,
    schedule: OrderSchedule | None = None,
) -> EpisodeLog:
    """Open-loop forward sim with shared ``model.day_step`` and SIM-04 logs.

    Non-order days coerce base-stock qty to 0 (T-079; matches closed-loop gate).
    Default burn-in is weekly-aligned (28 days) under periodic MWF age.
    """
    p = params or ModelParams()
    sched = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
    ships = shipments if shipments is not None else load_abdella_shipments()
    cohorts: list[Cohort] = []
    next_lot_id = 1
    # Pipeline: order placed on day t arrives as delivery on day t+lead_time.
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score

    for day in range(horizon):
        on_hand = sum(c.n for c in cohorts)
        order_qty = open_loop_order(on_hand, S=S)
        # Round to whole cases for physical delivery; M1 still uses unit counts.
        # Ceil (not nearest): intentional fork vs closed-loop ``case_round``.
        cases = int(np.ceil(order_qty / p.case_size)) if order_qty > 0 else 0
        order_units = cases * p.case_size
        if not sched.can_order(day):
            order_units = 0
        enqueue_pending_order(pending, day, lead_time, order_units)

        arrival_units = pop_arrival_units(pending, day)
        delivery: Cohort | None = None
        age_at_receipt: float | None = None
        pack_date = None
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
