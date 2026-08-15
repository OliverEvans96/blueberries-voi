"""Shared model types and constitutive formulas (viz / diagnostics).

Hot compute (``day_step``, session advance, VOI CRN) lives in ``voi_core`` after
T-121 Wave F (ADR 0127).
"""

from __future__ import annotations

from blueberries_voi.model.constitutive import (
    allocate_sales,
    death_prob_hazard_product,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
    weibull_survival,
)
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.model.params import Cohort, DayStepResult, ModelParams
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL
from blueberries_voi.sim.rust_bridge import day_step

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
