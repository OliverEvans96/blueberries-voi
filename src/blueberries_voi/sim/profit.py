"""SIM-01=B day / episode profit helpers (pure numeric; no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueberries_voi.sim import DayLog, EpisodeLog

__all__ = [
    "DEFAULT_PROFIT_COSTS",
    "DEFAULT_STORE_ECONOMICS",
    "STUDIO_PROFIT_COSTS",
    "ProfitCosts",
    "StoreEconomics",
    "day_profit",
    "day_profit_store",
    "episode_profit",
    "profit_costs_from_store_economics",
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


@dataclass(frozen=True)
class StoreEconomics:
    """Studio-style per-unit money knobs (not filter observations)."""

    sell_price: float
    purchase_cost: float
    waste_cost: float
    stockout_penalty: float


DEFAULT_STORE_ECONOMICS = StoreEconomics(
    sell_price=4.5,
    purchase_cost=1.8,
    waste_cost=1.2,
    stockout_penalty=2.5,
)


def profit_costs_from_store_economics(economics: StoreEconomics) -> ProfitCosts:
    """Map Studio economics to scaffold ``ProfitCosts`` (net margin per sale)."""
    return ProfitCosts(
        unit_margin=float(economics.sell_price - economics.purchase_cost),
        waste_cost=float(economics.waste_cost),
        stockout_penalty=float(economics.stockout_penalty),
    )


# Notebook / channel_joint closed-loop profit defaults (matches web mock generate.ts).
STUDIO_PROFIT_COSTS = profit_costs_from_store_economics(DEFAULT_STORE_ECONOMICS)


def day_profit_store(day: DayLog, economics: StoreEconomics) -> float:
    """Studio P&L: revenue minus purchase, waste, and stockout costs."""
    lost = max(0, day.demand - day.sales_total)
    revenue = economics.sell_price * day.sales_total
    costs = (
        economics.purchase_cost * day.arrivals
        + economics.waste_cost * day.waste_total
        + economics.stockout_penalty * lost
    )
    return float(revenue - costs)
