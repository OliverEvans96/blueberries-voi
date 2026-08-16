"""Filter package — observation types and f-native belief façades (ADR 0130 / 0131).

Production filter stepping lives in ``voi_core`` (unit PF). This package exposes
observation masks, belief wire helpers, and backend selection constants.
"""

from __future__ import annotations

from blueberries_voi.filter.belief import (
    ShelfBelief,
    effective_inventory,
    empty_shelf_belief,
    flatten_shelf_belief,
    shelf_belief_from_cohorts_oracle,
    shelf_belief_from_oracle,
    unflatten_shelf_belief,
)
from blueberries_voi.filter.constants import (
    PRODUCTION_BACKEND,
    PRODUCTION_ESS_FRACTION,
    PRODUCTION_K,
    PRODUCTION_L,
    PRODUCTION_N,
)
from blueberries_voi.filter.l_fallback import BackendChoice, choose_backend
from blueberries_voi.filter.types import (
    UNOBSERVED,
    FilterSummary,
    ObsMask,
    P1Obs,
    RichObs,
    is_unobserved,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.sim.rust_bridge import day_step

__all__ = [
    "PRODUCTION_BACKEND",
    "PRODUCTION_ESS_FRACTION",
    "PRODUCTION_K",
    "PRODUCTION_L",
    "PRODUCTION_N",
    "UNOBSERVED",
    "BackendChoice",
    "FilterSummary",
    "ObsMask",
    "P1Obs",
    "RichObs",
    "ShelfBelief",
    "choose_backend",
    "day_step",
    "effective_inventory",
    "empty_shelf_belief",
    "flatten_shelf_belief",
    "is_unobserved",
    "mask_for",
    "rich_obs_from_day_log",
    "shelf_belief_from_cohorts_oracle",
    "shelf_belief_from_oracle",
    "unflatten_shelf_belief",
]
