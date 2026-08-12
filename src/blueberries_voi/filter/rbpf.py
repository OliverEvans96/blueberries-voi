"""Production RBPF (FIL-01 / T-006) after FIL-13 settle at measured L."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from blueberries_voi.filter.backends import (
    FullJointBackend,
    ParticleState,
)
from blueberries_voi.filter.backends import (
    ess as ess_fn,
)
from blueberries_voi.filter.types import (
    FilterSummary,
    P1Obs,
    age_grid,
    guard_joint_memory,
)
from blueberries_voi.model import ModelParams, day_step
from blueberries_voi.rng import STREAM_FILTER_RESAMPLE, spawn_rng

if TYPE_CHECKING:
    import numpy as np

# Production numerics after FIL-13/15 settle (ADR 0082/0083).
PRODUCTION_BACKEND: str = "full_joint"
PRODUCTION_K: int = 8
PRODUCTION_N: int = 2000
PRODUCTION_ESS_FRACTION: float = 0.5
# Measured L under M1 open-loop is ≤3; keep headroom for short spikes.
PRODUCTION_L: int = 3


@dataclass
class RBPF:
    """Rao-Blackwellised PF: sample counts, marginalise joint age on a grid."""

    params: ModelParams
    N: int = PRODUCTION_N
    K: int = PRODUCTION_K
    ess_fraction: float = PRODUCTION_ESS_FRACTION
    L: int = PRODUCTION_L
    _backend: FullJointBackend = field(default_factory=FullJointBackend)
    _state: ParticleState | None = None
    _day: int = 0
    _root_seed: int = 0
    _run_id: str | int = "rbpf"

    def __post_init__(self) -> None:
        guard_joint_memory(self.K, self.L, self.N)

    def initialize(self, rng: np.random.Generator, *, L: int | None = None) -> None:
        if L is not None:
            self.L = L
            guard_joint_memory(self.K, self.L, self.N)
        self._state = self._backend.initialize(
            N=self.N, K=self.K, L=self.L, params=self.params, rng=rng
        )
        self._day = 0

    def step(self, obs: P1Obs, rng: np.random.Generator | None = None) -> FilterSummary:
        if self._state is None:
            msg = "RBPF.initialize must be called before step"
            raise RuntimeError(msg)
        if rng is None:
            rng = spawn_rng(
                self._root_seed,
                run_id=self._run_id,
                day=self._day,
                stream=STREAM_FILTER_RESAMPLE,
            )
        self._state = self._backend.predict_update(self._state, obs, self.params, rng)
        e = ess_fn(self._state.weights)
        self._day += 1
        return FilterSummary(ess=e, mean_L=float(self._state.L), log_lik=0.0)

    def age_posterior(self, lot_index: int = 0) -> np.ndarray:
        if self._state is None:
            msg = "RBPF.initialize must be called before age_posterior"
            raise RuntimeError(msg)
        post = self._state.age_post[:, lot_index, :]
        w = self._state.weights[:, None]
        marg = (w * post).sum(axis=0)
        out = marg / max(float(marg.sum()), 1e-300)
        return cast("np.ndarray", out)


__all__ = [
    "PRODUCTION_BACKEND",
    "PRODUCTION_ESS_FRACTION",
    "PRODUCTION_K",
    "PRODUCTION_L",
    "PRODUCTION_N",
    "RBPF",
    "FilterSummary",
    "P1Obs",
    "age_grid",
    "day_step",
]
