"""Shared model kernels (MOD-12 day_step and constitutive physics).

Calendar demand (ADR 0113 / 0113 / T-082)
----------------------------------------
* ``ModelParams.demand_profile`` — optional loaded ``DemandProfile`` (JSON product).
* ``draw_demand(rng, params, *, day=None)`` — when ``day`` is set and a profile is
  configured, NB mean is ``profile.mu(day)``; when ``day`` is ``None`` (or no
  profile), mean stays constant ``demand_mu`` (A2 / pre-CAL compat).
* ``day_step(..., day=None)`` forwards episode day into ``draw_demand`` when
  demand is not pre-drawn.
"""

from __future__ import annotations

from typing import Any

from blueberries_voi.model.day_step import day_step
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.model.params import Cohort, DayStepResult, ModelParams
from blueberries_voi.model.physics import (
    allocate_sales,
    death_prob_hazard_product,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
    weibull_survival,
)
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL

# Re-export stream names used by callers wiring day_step RNGs.
__all__ = [
    "STREAM_ALLOC",
    "STREAM_DEMAND",
    "STREAM_SPOIL",
    "Cohort",
    "DayStepResult",
    "DemandProfile",
    "ModelParams",
    "allocate_sales",
    "day_step",
    "death_prob_hazard_product",
    "death_prob_survival_ratio",
    "draw_demand",
    "load_demand_profile",
    "picking_weights",
    "q10_age_increment",
    "weibull_survival",
]


def _shared_day_step_symbol() -> Any:
    """Identity used by shared-import gate tests."""
    return day_step
