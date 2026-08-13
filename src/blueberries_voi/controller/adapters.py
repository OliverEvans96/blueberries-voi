"""Adapters that present controller policies as closed-loop day-first orderers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blueberries_voi.controller.damped_sw import (
    DampedSurvivalWeightedPolicy,
    _protection_demand_quantile,
)
from blueberries_voi.controller.ordering import ConstantOrderPolicy
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.filter.belief import ShelfBelief
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE

if TYPE_CHECKING:
    from collections.abc import Mapping

    from blueberries_voi.model import ModelParams
    from blueberries_voi.sim.order_schedule import OrderSchedule


def _empty_shelf_belief(_params: ModelParams) -> ShelfBelief:
    """Empty-shelf fallback when order() receives a non-ShelfBelief belief."""
    grid = [0.0, 2.0, 4.0, 6.0, 8.0]
    return ShelfBelief(lot_counts=[], age_marginals=[], tau_grid=grid)


class _ClosedLoopPolicyAdapter:
    """Adapt controller policies to ``sim.episode.Policy`` call shape."""

    def __init__(
        self,
        arm_id: str,
        alpha: float,
        params: ModelParams,
        *,
        schedule: OrderSchedule | None = None,
    ) -> None:
        self.arm_id = arm_id
        self.alpha = float(alpha)
        self.params = params
        self.schedule = DEFAULT_ORDER_SCHEDULE if schedule is None else schedule
        # Seed demand_target from a representative order-day protection length.
        seed_day = next(
            (d for d in range(7) if self.schedule.can_order(d)),
            0,
        )
        prot = int(self.schedule.protection_days(seed_day))
        d_star = _protection_demand_quantile(self.alpha, params, protection_days=prot)
        if arm_id == "constant":
            # Constant order = case-rounded protection-interval fractile at alpha.
            self._inner: Any = ConstantOrderPolicy(
                round(d_star), case_size=int(params.case_size)
            )
            self._kind = "constant"
        elif arm_id == "rung0":
            self._inner = CorrectedAgeBlindPolicy(
                alpha=self.alpha,
                params=params,
                demand_target=d_star,
                case_size=int(params.case_size),
                schedule=self.schedule,
            )
            self._kind = "rung0"
        elif arm_id == "sw":
            self._inner = DampedSurvivalWeightedPolicy(
                alpha=self.alpha,
                params=params,
                schedule=self.schedule,
            )
            self._kind = "sw"
        else:
            msg = f"no closed-loop adapter for arm {arm_id!r}"
            raise ValueError(msg)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        pending = pending_orders if pending_orders is not None else {}
        if self._kind == "constant":
            return int(self._inner.order(belief, day=day, pending_orders=()))
        if self._kind == "rung0":
            return int(self._inner.order(day, belief, pending_orders=pending))
        shelf = (
            belief
            if isinstance(belief, ShelfBelief)
            else _empty_shelf_belief(self.params)
        )
        return int(self._inner.order(shelf, day=day, pending_orders=pending))


__all__ = [
    "_ClosedLoopPolicyAdapter",
]
