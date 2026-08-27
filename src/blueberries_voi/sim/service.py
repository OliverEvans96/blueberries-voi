"""Service-level metrics from controller step logs (T-164)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueberries_voi.sim.types_log import ControllerStepLog


@dataclass(frozen=True)
class ServiceMetrics:
    """Fill rate and day-level no-stockout rate over scored days."""

    fill_rate: float
    day_no_stockout_rate: float
    scored_days: int


def service_metrics_from_steps(steps: list[ControllerStepLog]) -> ServiceMetrics:
    """Aggregate fill rate and Pr(no stockout) from per-day controller logs."""
    if not steps:
        return ServiceMetrics(fill_rate=0.0, day_no_stockout_rate=0.0, scored_days=0)
    demand = sum(s.demand for s in steps)
    sales = sum(s.sales_total for s in steps)
    fill = sales / demand if demand > 0 else 1.0
    no_stockout_days = sum(1 for s in steps if s.sales_total >= s.demand)
    return ServiceMetrics(
        fill_rate=float(fill),
        day_no_stockout_rate=no_stockout_days / len(steps),
        scored_days=len(steps),
    )
