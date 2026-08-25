"""Store section doc figure renderers."""

from __future__ import annotations

from .demand_calendar import render as render_demand_calendar
from .gamma_aging import render as render_gamma_aging
from .picking_weights import render as render_picking_weights
from .spoilage_trajectories import render as render_spoilage_trajectories

__all__ = [
    "render_demand_calendar",
    "render_gamma_aging",
    "render_picking_weights",
    "render_spoilage_trajectories",
]
