"""Interactive simulator façade for dual-runtime hosts (ADR 0099 / 0100 / 0127).

``EngineSession`` exposes ``init`` / ``step`` / ``step_n`` / ``reset`` / ``act``
returning Snapshot and DayDelta JSON dicts with flat belief buffers. Hot compute
is Rust-only after T-121 Wave F.
"""

from __future__ import annotations

from blueberries_voi.simulator.session import (
    BROWSER_DEMO_BUDGETS,
    DEMO_BUDGETS,
    EngineSession,
)

__all__ = [
    "BROWSER_DEMO_BUDGETS",
    "DEMO_BUDGETS",
    "EngineSession",
]
