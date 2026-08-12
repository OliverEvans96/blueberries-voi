"""Forward simulator, arrival generator, and SIM-04 logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from blueberries_voi.model import Cohort, ModelParams, day_step
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

# Fixed episode calendar epoch for synthetic ASN pack dates (T-019).
# Receipt day = epoch + episode day index; pack_date = receipt - round(tau_in).
# Deterministic under CRN; Abdella traces do not ship real ASN calendars.
_EPISODE_CALENDAR_EPOCH: date = date(2024, 1, 1)

__all__ = [
    "DayLog",
    "EpisodeLog",
    "LotState",
    "day_step",
    "generate_arrival_age",
    "open_loop_order",
    "run_episode",
]


@dataclass
class LotState:
    n: int
    tau: float
    lot_id: int


@dataclass
class DayLog:
    """SIM-04 ground-truth day record."""

    day: int
    lots: list[LotState]
    sales_total: int
    waste_total: int
    arrivals: int
    order_qty: int
    demand: int
    L: int
    # M2.5 rich emit (SIM-04): per-lot maps + delivery receipt metadata.
    sales_by_lot: dict[int, int] = field(default_factory=dict)
    waste_by_lot: dict[int, int] = field(default_factory=dict)
    age_at_receipt: float | None = None
    pack_date: date | None = None


@dataclass
class EpisodeLog:
    days: list[DayLog] = field(default_factory=list)
    n_burn: int = 0
    n_score: int = 0

    @property
    def scored(self) -> list[DayLog]:
        return self.days[self.n_burn :]


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
    n_burn: int = 30,
    n_score: int = 90,
    S: int = 60,
    lead_time: int = 1,
    spread_scale: float = 1.0,
    shipments: list[ShipmentTrace] | None = None,
) -> EpisodeLog:
    """Open-loop forward sim with shared ``model.day_step`` and SIM-04 logs."""
    p = params or ModelParams()
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
        cases = int(np.ceil(order_qty / p.case_size)) if order_qty > 0 else 0
        order_units = cases * p.case_size
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
            # Synthetic ASN calendar: receipt on epoch+day, pack back by transit age.
            receipt_day = _EPISODE_CALENDAR_EPOCH + timedelta(days=day)
            transit_days = max(round(age_at_receipt), 0)
            pack_date = receipt_day - timedelta(days=transit_days)

        # Lot ids aligned with day_step sales_by_cohort / waste_by_cohort indices
        # (live start-of-day cohorts only; delivery is post-spoil).
        pre_live_ids = [c.lot_id for c in cohorts if c.n > 0]
        rng_d = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_SPOIL)
        result = day_step(
            cohorts,
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
