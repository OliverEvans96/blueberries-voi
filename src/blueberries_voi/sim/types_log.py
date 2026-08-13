"""SIM-04 ground-truth lot / day / episode log types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


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
    # M1.5 rich emit (SIM-04): per-lot maps + delivery receipt metadata.
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


__all__ = [
    "DayLog",
    "EpisodeLog",
    "LotState",
]
