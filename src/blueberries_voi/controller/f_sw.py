"""f-native damped survival-weighted base-stock (ADR 0130 / T-C2-A)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueberries_voi.filter.belief import ShelfBelief, effective_inventory
from blueberries_voi.sim.bakeoff_damped_sw import protection_demand_quantile
from blueberries_voi.sim.bakeoff_ordering import case_round

if TYPE_CHECKING:
    from collections.abc import Mapping

    from blueberries_voi.model import ModelParams
    from blueberries_voi.sim.order_schedule import OrderSchedule

_PROTECTION_DEMAND_DAYS = 2


def damped_sw_order_f_belief(
    belief: ShelfBelief,
    *,
    pending_orders: Mapping[int, int],
    params: ModelParams,
    alpha: float,
    rho: float,
    f_pipeline_default: float = 1.0,
    day: int = 0,
    schedule: OrderSchedule | None = None,
) -> int:
    """Case-rounded damped SW order from f-belief."""
    if schedule is not None and not schedule.can_order(day):
        return 0
    i_tilde = effective_inventory(
        belief,
        pending_orders=pending_orders,
        f_pipeline_default=f_pipeline_default,
    )
    if schedule is not None:
        n_days = int(schedule.protection_days(day))
    else:
        n_days = _PROTECTION_DEMAND_DAYS
    d_star = protection_demand_quantile(alpha, params, protection_days=n_days)
    raw = rho * max(0.0, d_star - i_tilde)
    return int(case_round(raw, params.case_size))


__all__ = ["damped_sw_order_f_belief"]
