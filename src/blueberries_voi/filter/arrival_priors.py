"""Cohort-birth arrival-age priors (SCN-F2a / SCN-F2; plan §3.3).

Writes only into the delivery ``age_post`` channel — no sales/waste soft terms.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from blueberries_voi.filter.types import is_unobserved

if TYPE_CHECKING:
    from blueberries_voi.filter.types import RichObs
    from blueberries_voi.model import ModelParams

# Documented default transit-uncertainty width for F2a (T-013 open question).
# Must keep F2a SD strictly below the cold Abdella mix under the Stage A grid.
F2A_TRANSIT_UNCERTAINTY_SD: float = 0.75


def _normalize(weights: np.ndarray) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    return w / max(float(w.sum()), 1e-300)


def _histogram_on_grid(ages: np.ndarray, grid: np.ndarray) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    half = (g[1] - g[0]) / 2.0
    edges = np.concatenate([[g[0] - half], (g[:-1] + g[1:]) / 2.0, [g[-1] + half]])
    hist, _ = np.histogram(np.clip(ages, g[0], g[-1]), bins=edges)
    return _normalize(hist.astype(float))


def _gaussian_on_grid(grid: np.ndarray, mean: float, sd: float) -> np.ndarray:
    g = np.asarray(grid, dtype=float)
    width = max(float(sd), 1e-9)
    log_w = -0.5 * ((g - float(mean)) / width) ** 2
    log_w -= float(log_w.max())
    return _normalize(np.exp(log_w))


@lru_cache(maxsize=8)
def _abdella_arrival_ages(q10: float, t_ref_c: float) -> tuple[float, ...]:
    # Lazy: keep interactive filter import free of eager Abdella parquet I/O.
    from blueberries_voi.model.abdella import (
        default_abdella_root,
        load_abdella_shipments,
        shipment_arrival_age,
    )

    ships = load_abdella_shipments(default_abdella_root())
    return tuple(
        float(shipment_arrival_age(s, q10=q10, t_ref_c=t_ref_c)) for s in ships
    )


def cold_abdella_arrival_age_prior(
    grid: np.ndarray,
    params: ModelParams,
) -> np.ndarray:
    """Baseline cold-chain mix on ``grid`` (Abdella bootstrap histogram)."""
    ages = np.asarray(
        _abdella_arrival_ages(params.q10, params.t_ref_c),
        dtype=float,
    )
    return _histogram_on_grid(ages, grid)


def arrival_age_prior_f2a(
    pack_date: date,
    *,
    grid: np.ndarray,
    params: ModelParams,
    as_of: date | None = None,
    receipt_date: date | None = None,
) -> np.ndarray:
    """Length-K prior narrowed from ASN pack date + transit uncertainty.

    Calendar transit days ``(receipt - pack)`` locate the prior when a receipt
    day is supplied; otherwise the centre falls back to the cold-mix mean age
    while retaining the documented F2a width (still narrower than the cold mix).
    """
    receipt = as_of if as_of is not None else receipt_date
    if receipt is not None:
        mean = float(max((receipt - pack_date).days, 0))
    else:
        ages = np.asarray(
            _abdella_arrival_ages(params.q10, params.t_ref_c),
            dtype=float,
        )
        mean = float(ages.mean())
    return _gaussian_on_grid(grid, mean, F2A_TRANSIT_UNCERTAINTY_SD)


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
    "F2A_TRANSIT_UNCERTAINTY_SD",
    "arrival_age_prior_f2",
    "arrival_age_prior_f2a",
    "cold_abdella_arrival_age_prior",
    "delivery_birth_age_prior",
]
