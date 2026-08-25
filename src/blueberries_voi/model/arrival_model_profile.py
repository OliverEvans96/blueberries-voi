"""Load committed Abdella arrival_model.json and sample priors (ADR 0148).

Stdlib JSON only at import time — no parquet. Used by legacy Python filter helpers
that still operate on an age/exposure grid.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

_DEFAULT_ARTIFACT = (
    Path(__file__).resolve().parents[3] / "data" / "abdella" / "arrival_model.json"
)


@lru_cache(maxsize=1)
def default_arrival_model_path() -> Path:
    return _DEFAULT_ARTIFACT


@lru_cache(maxsize=1)
def load_arrival_model(path: Path | str | None = None) -> dict[str, Any]:
    """Load committed arrival_model.json."""
    p = Path(path) if path is not None else default_arrival_model_path()
    raw: Any = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "arrival_model.json root must be a JSON object"
        raise ValueError(msg)
    return raw


def _phi_bar_from_t_bar(t_bar: float, q10: float, t_ref: float) -> float:
    return float(math.pow(q10, (t_bar - t_ref) / 10.0))


def _sample_exposure(
    rng: np.random.Generator,
    payload: dict[str, Any],
    *,
    corridor_key: str,
    n: int,
) -> np.ndarray:
    corridor = payload["corridors"][corridor_key]
    d_min = float(corridor["d_min"])
    delay_shape = float(corridor["delay_shape"])
    delay_scale = float(corridor["delay_scale"])
    mu_t = float(payload["mu_T"])
    sigma_t = float(payload["sigma_T"])
    temp_floor = float(payload.get("temp_floor_c", 0.0))
    sigma_pos = float(payload["sigma_pos"])
    q10 = float(payload["q10"])
    t_ref = float(payload["T_ref"])

    delays = rng.gamma(delay_shape, delay_scale, size=n)
    d = d_min + delays
    t_bar = rng.normal(mu_t, sigma_t, size=n)
    t_bar = np.maximum(t_bar, temp_floor)
    phi_bar = np.power(q10, (t_bar - t_ref) / 10.0)
    psi = rng.lognormal(0.0, sigma_pos, size=n)
    return d * phi_bar * psi


def exposure_prior_on_grid(
    grid: np.ndarray,
    payload: dict[str, Any] | None = None,
    *,
    corridor_key: str = "abdella_all",
    n_samples: int = 400,
    seed: int = 7,
) -> np.ndarray:
    """Discrete prior on ``grid`` from Monte Carlo on the committed arrival model."""
    art = payload if payload is not None else load_arrival_model()
    rng = np.random.default_rng(seed)
    exposures = _sample_exposure(rng, art, corridor_key=corridor_key, n=n_samples)
    g = np.asarray(grid, dtype=float)
    half = (g[1] - g[0]) / 2.0
    edges = np.concatenate([[g[0] - half], (g[:-1] + g[1:]) / 2.0, [g[-1] + half]])
    hist, _ = np.histogram(np.clip(exposures, g[0], g[-1]), bins=edges)
    prior = hist.astype(float)
    return prior / max(float(prior.sum()), 1e-300)


def phi_bar_fleet_moments(
    payload: dict[str, Any] | None = None,
    *,
    n_samples: int = 10_000,
    seed: int = 11,
) -> tuple[float, float]:
    """Mean and sd of duration-averaged phi_bar from truncated-normal transit temps."""
    art = payload if payload is not None else load_arrival_model()
    rng = np.random.default_rng(seed)
    mu_t = float(art["mu_T"])
    sigma_t = float(art["sigma_T"])
    temp_floor = float(art.get("temp_floor_c", 0.0))
    q10 = float(art["q10"])
    t_ref = float(art["T_ref"])
    t_bar = rng.normal(mu_t, sigma_t, size=n_samples)
    t_bar = np.maximum(t_bar, temp_floor)
    phi = np.power(q10, (t_bar - t_ref) / 10.0)
    return float(phi.mean()), float(phi.std(ddof=0))


__all__ = [
    "default_arrival_model_path",
    "exposure_prior_on_grid",
    "load_arrival_model",
    "phi_bar_fleet_moments",
]
