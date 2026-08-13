"""FIL-11 shared metrics / paths (peeled from viz.fil11)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from blueberries_voi.filter.types import age_grid
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "figures" / "m1.5"

# Documented Stage B coverage band around nominal 90% (diagnostic, not gate).
STAGE_B_COVERAGE_LO = 0.70
STAGE_B_COVERAGE_HI = 0.99
# Default generative Stage C TV / CRN-divergence tolerance (ADR 0088 / T-012).
STAGE_C_TV_TOL = 0.05
_STAGE_C_SEED = 202_608_12


def _spread(post: np.ndarray, grid: np.ndarray) -> float:
    mean = float(np.sum(grid * post))
    var = float(np.sum(post * (grid - mean) ** 2))
    return float(np.sqrt(max(var, 0.0)))


def _arrival_prior(spread_scale: float, K: int, n_samples: int = 400) -> np.ndarray:
    """Discrete arrival-age prior under a given spread_scale (bootstrap mix)."""
    from blueberries_voi.model.abdella import shipment_arrival_age

    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    params = ModelParams()
    base = np.array(
        [shipment_arrival_age(s, q10=params.q10, t_ref_c=params.t_ref_c) for s in ships]
    )
    mean_age = float(base.mean())
    rng = np.random.default_rng(7)
    ages_a = mean_age + spread_scale * (rng.choice(base, size=n_samples) - mean_age)
    grid = age_grid(K)
    half = (grid[1] - grid[0]) / 2
    edges = np.concatenate(
        [[grid[0] - half], (grid[:-1] + grid[1:]) / 2, [grid[-1] + half]]
    )
    hist, _ = np.histogram(np.clip(ages_a, grid[0], grid[-1]), bins=edges)
    prior = hist.astype(float)
    return prior / max(float(prior.sum()), 1e-300)
