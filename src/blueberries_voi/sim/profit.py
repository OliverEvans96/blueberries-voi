"""SIM-01=B day / episode profit helpers (pure numeric; no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueberries_voi.sim import DayLog, EpisodeLog

__all__ = [
    "DEFAULT_PROFIT_COSTS",
    "ProfitCosts",
    "day_profit",
    "episode_profit",
]


@dataclass(frozen=True)
class ProfitCosts:
    """Cost parameters for SIM-01=B day profit."""

    unit_margin: float
    waste_cost: float
    stockout_penalty: float


# Uncalibrated scaffold costs for VOI / M2 / alpha-tune when callers omit ``costs``.
# These are not fitted blueberry store economics (ADR 0104).
DEFAULT_PROFIT_COSTS = ProfitCosts(
    unit_margin=2.0,
    waste_cost=1.5,
    stockout_penalty=3.0,
)


def day_profit(day: DayLog, costs: ProfitCosts) -> float:
    """Day profit: margin * sales - waste_cost * waste - stockout * lost sales.

    Lost sales = max(0, demand - sales). Holding / on-hand is not charged.
    """
    sales = day.sales_total
    waste = day.waste_total
    lost = max(0, day.demand - sales)
    return (
        costs.unit_margin * sales
        - costs.waste_cost * waste
        - costs.stockout_penalty * lost
    )


def episode_profit(episode: EpisodeLog, costs: ProfitCosts) -> float:
    """Sum day profits over scored days only (after SIM-03 burn-in)."""
    return sum(day_profit(day, costs) for day in episode.scored)
