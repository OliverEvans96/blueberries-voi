"""Corrected age-blind Rung 0 baseline (Nahmias / CTL-05).

Observes **total on-hand only** (not ages) plus the order pipeline, then
applies a stationary expected-outdating / mean-survival correction before a
base-stock order. This is the honest competitor to age-aware survival-weighted
policies — not a naive count of units on hand.

Formula (CTL-05 / X-12 fixture lock for daily delivery, lead time 1):

    I^{R0} = \\bar{w} \\cdot N + \\sum_j q_j \\, w_{\\mathrm{pipe}}
    q = \\mathrm{case\\_round}\\big(\\rho [d^\\star - I^{R0}]^+\\big)

where ``N`` is total on-hand, ``\\bar{w}`` is the mean survival weight under the
stationary age distribution (outdating correction), ``w_pipe`` weights pending
orders, ``d^\\star`` is the protection-interval demand fractile
``F^{-1}_{D_{t:t+L}}(\\alpha)``, and ``\\rho`` is optional damping (Rung 0 default
``\\rho=1``).

Protection interval: under X-11 daily delivery with LT=1, ``\\Delta\\tau_L`` covers
**2** days of demand (``protection_days=2``). When survival weights are constant
(``\\beta=1`` / flat ``w``), this coincides with survival-weighted base-stock on
the same protection interval after ``case_round``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.model import ModelParams

if TYPE_CHECKING:
    from collections.abc import Mapping


class CorrectedAgeBlindPolicy:
    """Nahmias-style corrected age-blind base-stock (Rung 0).

    Orders from total on-hand (+ pipeline) with mean-survival outdating
    correction; ignores age mix.
    """

    def __init__(
        self,
        *,
        alpha: float = 0.9,
        params: ModelParams | None = None,
        rho: float = 1.0,
        mean_survival_weight: float = 0.75,
        pipeline_weight: float = 0.75,
        demand_target: float | None = None,
        protection_days: int = 2,
        case_size: int | None = None,
    ) -> None:
        self.alpha = float(alpha)
        self.params = params or ModelParams()
        self.rho = float(rho)
        self.mean_survival_weight = float(mean_survival_weight)
        self.pipeline_weight = float(pipeline_weight)
        self.protection_days = int(protection_days)
        self.case_size = (
            int(case_size) if case_size is not None else int(self.params.case_size)
        )
        # Injectable F^{-1} until demand helpers land (T-028/T-029).
        self.demand_target = float(demand_target) if demand_target is not None else 0.0

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        del day  # age-blind base-stock does not use calendar day
        total_on_hand = _total_on_hand(belief)
        pending = pending_orders or {}
        inv = self.mean_survival_weight * total_on_hand + sum(
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
