"""Interactive simulator façade for dual-runtime hosts (ADR 0097 / 0098).

``EngineSession`` exposes ``init`` / ``step`` / ``step_n`` / ``reset`` / ``act``
returning Snapshot and DayDelta JSON dicts with flat belief buffers. Presentation
economics, PnL, ghost, and heatmap stay on the JS side.

Minimal ``Day`` chart fields (open until T-045 goldens): ``day``, ``order_qty``,
``arrivals``, ``sales_total``, ``waste_total``, ``demand``, ``L``.
"""

from __future__ import annotations

from blueberries_voi.simulator.day_driver import advance_day
from blueberries_voi.simulator.session import (
    BROWSER_DEMO_BUDGETS,
    DEMO_BUDGETS,
    EngineSession,
)

__all__ = [
    "BROWSER_DEMO_BUDGETS",
    "DEMO_BUDGETS",
    "EngineSession",
    "advance_day",
]
