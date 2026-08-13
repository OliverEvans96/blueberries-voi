"""Shared day-tick primitives for episode / open-loop / day_driver / VOI / M2.

Call sites keep their own order rounding, OrderSchedule gating, and whether
``day_step`` receives ``day=`` — those forks are intentional (ADR 0118).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from blueberries_voi.sim.calendar import _EPISODE_CALENDAR_EPOCH
from blueberries_voi.sim.types_log import LotState

if TYPE_CHECKING:
    from collections.abc import MutableMapping, Sequence

    import numpy as np

    from blueberries_voi.model import Cohort

__all__ = [
    "enqueue_pending_order",
    "lot_states_from_cohorts",
    "nonzero_lot_maps",
    "pack_date_from_epoch",
    "pop_arrival_units",
    "pre_live_lot_ids",
]


def enqueue_pending_order(
    pending: MutableMapping[int, int],
    day: int,
    lead_time: int,
    order_units: int,
) -> None:
    """Record ``order_units`` to arrive on ``day + lead_time``."""
    pending[day + lead_time] = pending.get(day + lead_time, 0) + order_units


def pop_arrival_units(pending: MutableMapping[int, int], day: int) -> int:
    """Units scheduled to arrive today; 0 if none."""
    return int(pending.pop(day, 0))


def pack_date_from_epoch(
    day: int,
    age_at_receipt: float,
    *,
    epoch: date | None = None,
) -> date:
    """Synthetic ASN pack date: ``epoch + day - round(tau_in)`` (T-019)."""
    base = _EPISODE_CALENDAR_EPOCH if epoch is None else epoch
    receipt_day = base + timedelta(days=day)
    transit_days = max(round(age_at_receipt), 0)
    return receipt_day - timedelta(days=transit_days)


def pre_live_lot_ids(cohorts: Sequence[Cohort]) -> list[int]:
    """Lot ids of start-of-day live cohorts (aligned with ``day_step`` maps)."""
    return [c.lot_id for c in cohorts if c.n > 0]


def nonzero_lot_maps(
    pre_live_ids: Sequence[int],
    sales_by_cohort: np.ndarray,
    waste_by_cohort: np.ndarray,
) -> tuple[dict[int, int], dict[int, int]]:
    """Map cohort-indexed sales/waste onto lot_id keys (zeros omitted)."""
    sales_by_lot = {
        int(pre_live_ids[i]): int(sales_by_cohort[i])
        for i in range(len(pre_live_ids))
        if int(sales_by_cohort[i]) != 0
    }
    waste_by_lot = {
        int(pre_live_ids[i]): int(waste_by_cohort[i])
        for i in range(len(pre_live_ids))
        if int(waste_by_cohort[i]) != 0
    }
    return sales_by_lot, waste_by_lot


def lot_states_from_cohorts(cohorts: Sequence[Cohort]) -> list[LotState]:
    """SIM-04 lot snapshot from live cohorts after ``day_step``."""
    return [LotState(n=c.n, tau=c.tau, lot_id=c.lot_id) for c in cohorts]
