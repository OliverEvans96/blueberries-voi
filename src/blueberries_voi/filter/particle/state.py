"""Particle state, backend protocol, ESS / resample helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from blueberries_voi.filter.types import P1Obs, RichObs, is_unobserved

if TYPE_CHECKING:
    from blueberries_voi.model import ModelParams


@dataclass
class ParticleState:
    """Particle state: counts sampled; arrival-age posterior marginalised (MOD-02)."""

    weights: np.ndarray  # (N,)
    counts: np.ndarray  # (N, L)
    age_idx: np.ndarray  # (N, L) for bootstrap PF
    age_post: np.ndarray  # (N, L, K) over arrival age τ_in
    days_on_shelf: np.ndarray  # (L,) calendar days since arrival
    L: int
    backend: str


class FilterBackend(Protocol):
    name: str

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState: ...

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState: ...


def _as_rich_obs(obs: RichObs | P1Obs) -> RichObs:
    if isinstance(obs, P1Obs):
        return RichObs.from_p1(obs)
    return obs


def _observed_int(value: object) -> int | None:
    """Return ``int(value)`` when observed; ``None`` when ``UNOBSERVED``."""
    if is_unobserved(value):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    msg = f"expected int observation, got {type(value)!r}"
    raise TypeError(msg)


def ess(weights: np.ndarray) -> float:
    w = weights / max(float(weights.sum()), 1e-300)
    return float(1.0 / np.sum(w**2))


def _systematic_resample(weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(weights)
    w = weights / max(float(weights.sum()), 1e-300)
    positions = (rng.random() + np.arange(n)) / n
    cumulative = np.cumsum(w)
    return np.searchsorted(cumulative, positions, side="right").astype(int)


def _prior_age_post(K: int, L: int, N: int) -> np.ndarray:
    return np.ones((N, L, K), dtype=float) / K


def _new_state(
    *,
    N: int,
    K: int,
    L: int,
    rng: np.random.Generator,
    backend: str,
) -> ParticleState:
    return ParticleState(
        weights=np.ones(N) / N,
        counts=rng.integers(0, 8, size=(N, L)),
        age_idx=rng.integers(0, K, size=(N, L)),
        age_post=_prior_age_post(K, L, N),
        days_on_shelf=np.zeros(L, dtype=float),
        L=L,
        backend=backend,
    )
