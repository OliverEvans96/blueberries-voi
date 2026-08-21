"""Order calendar: weekdays, next-order lookup, and protection length (CAL-A1).

Epoch clock matches the ASN episode calendar: day 0 = Monday 2024-01-01.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "DEFAULT_ORDER_SCHEDULE",
    "OrderSchedule",
    "derive_order_weekdays",
]

_EPOCH: date = date(2024, 1, 1)
_DEFAULT_DELIVERY = frozenset({0, 2, 4})
_DEFAULT_LEAD_TIME = 1
_DEFAULT_ORDER = frozenset({6, 1, 3})


def derive_order_weekdays(
    delivery_weekdays: Iterable[int] | frozenset[int],
    lead_time_days: int,
) -> frozenset[int]:
    """Derive order weekdays from delivery days and lead time (ADR 0142).

    ``order_weekday = (delivery - lead_time + 7) % 7`` for each delivery day;
    result is deduplicated and sorted implicitly via frozenset.
    """
    lt = int(lead_time_days)
    days = {int(d) for d in delivery_weekdays}
    if not days:
        msg = "delivery_weekdays must be non-empty"
        raise ValueError(msg)
    for day in days:
        if not 0 <= day <= 6:
            msg = f"delivery weekday must be 0..6 (monday0), got {day}"
            raise ValueError(msg)
    return frozenset((day - lt + 7) % 7 for day in days)


@dataclass(frozen=True)
class OrderSchedule:
    """MWF delivery / LT=1 / Sun-Tue-Thu orders (ADR 0114; configurable ADR 0142)."""

    delivery_weekdays: frozenset[int] = _DEFAULT_DELIVERY
    lead_time_days: int = _DEFAULT_LEAD_TIME
    order_weekdays: frozenset[int] = _DEFAULT_ORDER

    @classmethod
    def with_delivery(
        cls,
        delivery_weekdays: Iterable[int],
        *,
        lead_time_days: int = _DEFAULT_LEAD_TIME,
    ) -> OrderSchedule:
        """Build a schedule from delivery weekdays; order days are derived."""
        delivery = frozenset(int(d) for d in delivery_weekdays)
        order = derive_order_weekdays(delivery, lead_time_days)
        return cls(
            delivery_weekdays=delivery,
            lead_time_days=int(lead_time_days),
            order_weekdays=order,
        )

    from_delivery = with_delivery

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
        """Days until next order day plus lead time (3/3/4 at default Sun/Tue/Thu)."""
        return self.next_order_day(day) - day + self.lead_time_days


DEFAULT_ORDER_SCHEDULE: OrderSchedule = OrderSchedule()
