"""Corrected age-blind Rung 0 baseline (Nahmias / CTL-05).

Observes **total on-hand only** (not ages) plus the order pipeline, then
applies an expected-outdating / mean-survival correction before a base-stock
order. This is the honest competitor to age-aware survival-weighted policies —
not a naive count of units on hand.

Formula (CTL-05 / X-12; CAL-A3 day-index under MWF):

    I^{R0} = \\bar{w}(day) \\cdot N + \\sum_j q_j \\, w_{\\mathrm{pipe}}
    q = \\mathrm{case\\_round}\\big(\\rho [d^\\star - I^{R0}]^+\\big)

where ``N`` is total on-hand, ``\\bar{w}(day)`` is the **day-indexed** (periodic)
mean survival weight under the age-blind outdating correction, ``w_pipe``
weights pending orders, ``d^\\star`` is the protection-interval demand fractile,
and ``\\rho`` is optional damping (Rung 0 default ``\\rho=1``).

Protection length under daily LT=1 was scalar 2; under CAL-01 the episode /
SW path uses ``OrderSchedule.protection_days`` (3/3/4). Rung 0 still accepts
an injectable ``demand_target``; when an ``OrderSchedule`` is attached,
non-order days return quantity 0 (T-079 / T-081).

Homogeneous μ + day-varying protection length is allowed until T-084 /
CAL-B4 (heterogeneous / μ(day) upgrade). Survival weights are day-indexed
here even when values are still homogeneous across weekdays.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, timedelta
from typing import TYPE_CHECKING

from blueberries_voi.model import ModelParams
from blueberries_voi.sim.case_round import case_round

if TYPE_CHECKING:
    from blueberries_voi.sim.order_schedule import OrderSchedule

_EPOCH: date = date(2024, 1, 1)

SurvivalWeight = float | Mapping[int, float] | Callable[[int], float]


def _weekday(day: int) -> int:
    return (_EPOCH + timedelta(days=day)).weekday()


class CorrectedAgeBlindPolicy:
    """Nahmias-style corrected age-blind base-stock (Rung 0).

    Orders from total on-hand (+ pipeline) with mean-survival outdating
    correction; ignores age mix. ``mean_survival_weight`` may be a scalar,
    weekday/day ``Mapping``, or ``Callable[[int], float]`` (CAL-A3).
    """

    def __init__(
        self,
        *,
        alpha: float = 0.9,
        params: ModelParams | None = None,
        rho: float = 1.0,
        mean_survival_weight: SurvivalWeight = 0.75,
        pipeline_weight: float = 0.75,
        demand_target: float | None = None,
        protection_days: int = 2,
        case_size: int | None = None,
        schedule: OrderSchedule | None = None,
    ) -> None:
        self.alpha = float(alpha)
        self.params = params or ModelParams()
        self.rho = float(rho)
        self.mean_survival_weight: SurvivalWeight = mean_survival_weight
        self.pipeline_weight = float(pipeline_weight)
        self.protection_days = int(protection_days)
        self.schedule = schedule
        self.case_size = (
            int(case_size) if case_size is not None else int(self.params.case_size)
        )
        # Injectable F^{-1} until demand helpers land (T-028/T-029).
        self.demand_target = float(demand_target) if demand_target is not None else 0.0

        # Periodic weekday table when a CAL schedule is attached and weight is
        # still a homogeneous scalar — exposes day-index API (not float-only).
        if schedule is not None and isinstance(mean_survival_weight, (int, float)):
            w = float(mean_survival_weight)
            self.survival_weights_by_weekday: Mapping[int, float] = {
                d: w for d in range(7)
            }

    def mean_survival_weight_for_day(self, day: int) -> float:
        """Resolve day-indexed (or scalar) age-blind survival weight."""
        w = self.mean_survival_weight
        if callable(w):
            return float(w(day))
        if isinstance(w, Mapping):
            if day in w:
                return float(w[day])
            wd = _weekday(day)
            if wd in w:
                return float(w[wd])
            msg = f"day-indexed weight map missing day={day} / weekday={wd}"
            raise KeyError(msg)
        return float(w)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
        schedule: OrderSchedule | None = None,
    ) -> int:
        sched = schedule if schedule is not None else self.schedule
        if sched is not None and not sched.can_order(day):
            return 0
        total_on_hand = _total_on_hand(belief)
        pending = pending_orders or {}
        bar_w = self.mean_survival_weight_for_day(day)
        inv = bar_w * total_on_hand + sum(
            float(qty) * self.pipeline_weight for qty in pending.values()
        )
        raw = self.rho * max(0.0, self.demand_target - inv)
        return case_round(raw, self.case_size)


def _total_on_hand(belief: object | None) -> float:
    if belief is None:
        return 0.0
    lot_counts = getattr(belief, "lot_counts", None)
    if lot_counts is None:
        return 0.0
    return float(sum(float(x) for x in lot_counts))


__all__ = ["CorrectedAgeBlindPolicy"]
