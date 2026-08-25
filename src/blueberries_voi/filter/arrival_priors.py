"""Cohort-birth arrival-age priors (SCN-F2a / SCN-F2; ADR 0141 gamma arrival).

Writes only into the delivery ``age_post`` channel — no sales/waste soft terms.
Priors sample the committed ``arrival_model.json`` artifact (ADR 0148), not parquet.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.types import is_unobserved
from blueberries_voi.model.arrival_model_profile import (
    exposure_prior_on_grid,
    phi_bar_fleet_moments,
)

if TYPE_CHECKING:
    from blueberries_voi.filter.types import RichObs
    from blueberries_voi.model import ModelParams


def _normalize(weights: np.ndarray) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    return w / max(float(w.sum()), 1e-300)


def _gaussian_on_grid(grid: np.ndarray, mean: float, sd: float) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    width = max(float(sd), 1e-9)
    log_w = -0.5 * ((g - float(mean)) / width) ** 2
    log_w -= float(log_w.max())
    return _normalize(np.exp(log_w))


@lru_cache(maxsize=4)
def _fleet_phi_bar_moments() -> tuple[float, float]:
    return phi_bar_fleet_moments()


def cold_abdella_arrival_age_prior(
    grid: np.ndarray,
    params: ModelParams,
) -> np.ndarray:
    """Baseline cold-chain mix on ``grid`` from fitted arrival_model.json."""
    del params
    return exposure_prior_on_grid(grid, corridor_key="abdella_all")


def arrival_age_prior_f2a(
    pack_date: date,
    *,
    grid: np.ndarray,
    params: ModelParams,
    as_of: date | None = None,
    receipt_date: date | None = None,
) -> np.ndarray:
    """Pack-date prior: calendar transit days x fleet phi_bar (ADR 0141)."""
    phi_mean, phi_sd = _fleet_phi_bar_moments()
    receipt = as_of if as_of is not None else receipt_date
    if receipt is not None:
        calendar_d = float(max((receipt - pack_date).days, 0))
        mean_age = calendar_d * phi_mean
        sd_age = max(calendar_d * phi_sd, 1e-9)
    else:
        prior = exposure_prior_on_grid(grid, corridor_key="abdella_all")
        g = np.asarray(grid, dtype=float)
        mean_age = float(np.sum(g * prior))
        sd_age = max(float(np.sqrt(np.sum(prior * (g - mean_age) ** 2))), 1e-9)
    return _gaussian_on_grid(grid, mean_age, sd_age)


def arrival_age_prior_f2(
    age_at_receipt: float,
    *,
    grid: np.ndarray,
) -> np.ndarray:
    """Length-K Dirac prior on the grid bin containing ``age_at_receipt``."""
    g = np.asarray(grid, dtype=float)
    nearest = int(np.argmin(np.abs(g - float(age_at_receipt))))
    weights = np.zeros(len(g), dtype=float)
    weights[nearest] = 1.0
    return weights


def delivery_birth_age_prior(
    obs: RichObs,
    grid: np.ndarray,
    params: ModelParams,
) -> np.ndarray:
    """Select F2 / F2a / cold Abdella birth prior from masked ``RichObs`` fields."""
    age_raw = obs.age_at_receipt
    if not is_unobserved(age_raw) and isinstance(age_raw, (int, float, np.floating)):
        return arrival_age_prior_f2(float(age_raw), grid=grid)

    pack_raw = obs.pack_date
    if not is_unobserved(pack_raw) and isinstance(pack_raw, date):
        return arrival_age_prior_f2a(pack_raw, grid=grid, params=params)

    return cold_abdella_arrival_age_prior(grid, params)


__all__ = [
    "arrival_age_prior_f2",
    "arrival_age_prior_f2a",
    "cold_abdella_arrival_age_prior",
    "delivery_birth_age_prior",
]
