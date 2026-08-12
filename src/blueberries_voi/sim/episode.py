"""Closed-loop Policy-driven episode driver (T-024).

Requires injectable ``shipments=`` — no Abdella filesystem default on this path.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np

from blueberries_voi.model import Cohort, ModelParams, day_step
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_SPOIL,
    spawn_rng,
)

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


def case_round(order_qty: int, case_size: int) -> int:
    """Ceil order quantity to whole cases; zero stays zero."""
    qty = max(0, int(order_qty))
    if qty <= 0:
        return 0
    cases = int(np.ceil(qty / case_size))
    return cases * case_size


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
) -> EpisodeLog:
    """Policy-driven forward sim sharing ``model.day_step`` and SIM-04 logs.

    ``shipments`` is required and must be non-empty. This path never loads
    Abdella parquet from the filesystem.
    """
    if not shipments:
        msg = "shipments must be non-empty"
        raise ValueError(msg)

    p = params or ModelParams()
    ships = list(shipments)
    cohorts: list[Cohort] = []
    next_lot_id = 1
    pending: dict[int, int] = {}
    log = EpisodeLog(n_burn=n_burn, n_score=n_score)
    horizon = n_burn + n_score

    for day in range(horizon):
        # Snapshot pipeline before placing today's order (ADR 0092).
        pending_view: Mapping[int, int] = dict(pending)
        raw_qty = int(policy.order(day, None, pending_orders=pending_view))
        order_units = case_round(raw_qty, p.case_size)
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
