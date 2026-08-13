"""Order calendar: weekdays, next-order lookup, and protection length (CAL-A1).

Epoch clock matches the ASN episode calendar: day 0 = Monday 2024-01-01.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

__all__ = [
    "DEFAULT_ORDER_SCHEDULE",
    "OrderSchedule",
]

_EPOCH: date = date(2024, 1, 1)


@dataclass(frozen=True)
class OrderSchedule:
    """MWF delivery / LT=1 / Sun-Tue-Thu order schedule (ADR 0114)."""

    delivery_weekdays: frozenset[int] = frozenset({0, 2, 4})
    lead_time_days: int = 1
    order_weekdays: frozenset[int] = frozenset({6, 1, 3})

    def _weekday(self, day: int) -> int:
        return (_EPOCH + timedelta(days=day)).weekday()

    def can_order(self, day: int) -> bool:
        return self._weekday(day) in self.order_weekdays

    def next_order_day(self, day: int) -> int:
        candidate = day + 1
        while not self.can_order(candidate):
            candidate += 1
        return candidate

    def protection_days(self, day: int) -> int:
        """Days until next order day plus lead time (3/3/4 on Sun/Tue/Thu)."""
        return self.next_order_day(day) - day + self.lead_time_days


DEFAULT_ORDER_SCHEDULE: OrderSchedule = OrderSchedule()
