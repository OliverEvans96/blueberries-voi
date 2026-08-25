"""Control section doc figure renderers."""

from __future__ import annotations

from .alpha_tune import render as render_alpha_tune
from .effective_inventory import render as render_effective_inventory
from .protection_demand import render as render_protection_demand

__all__ = [
    "render_alpha_tune",
    "render_effective_inventory",
    "render_protection_demand",
]
