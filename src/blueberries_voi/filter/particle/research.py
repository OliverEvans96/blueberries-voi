"""Research particle filter for viz / experiments (not production hot path)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import numpy as np

from blueberries_voi.filter.backends import (
    CountsOnlyBackend,
    FilterBackend,
    ParticleState,
)
from blueberries_voi.filter.backends import ess as ess_fn
from blueberries_voi.filter.constants import PRODUCTION_K, PRODUCTION_L, PRODUCTION_N
from blueberries_voi.filter.l_fallback import BackendChoice, choose_backend
from blueberries_voi.filter.types import FilterSummary, P1Obs, RichObs
from blueberries_voi.rng import STREAM_FILTER_RESAMPLE, spawn_rng

if TYPE_CHECKING:
    from blueberries_voi.model import ModelParams


@dataclass
class ResearchParticleFilter:
    """Counts-only research PF: sample counts; arrival priors + MOD-02 clock."""

    params: ModelParams
    N: int = PRODUCTION_N
    K: int = PRODUCTION_K
    ess_fraction: float = 0.5
    L: int = PRODUCTION_L
    sales_likelihood: str = "exact_sequential_wor"
    _backend: FilterBackend = field(default_factory=CountsOnlyBackend)
    _state: ParticleState | None = None
    _day: int = 0
    _root_seed: int = 0
    _run_id: str | int = "particle_filter"
    backend_choice: BackendChoice = field(init=False)

    def __post_init__(self) -> None:
        self._apply_backend_choice()

    def _apply_backend_choice(self) -> None:
        """Always select counts_only; never truncate L (ADR 0105)."""
        choice = choose_backend(self.K, self.L, self.N)
        self.backend_choice = choice
        if choice.backend == "counts_only":
            self._backend = CountsOnlyBackend(sales_likelihood=self.sales_likelihood)

    def initialize(self, rng: np.random.Generator, *, L: int | None = None) -> None:
        if L is not None:
            self.L = L
        self._apply_backend_choice()
        self._state = self._backend.initialize(
            N=self.N, K=self.K, L=self.L, params=self.params, rng=rng
        )
        self._day = 0

    def step(
        self,
        obs: RichObs | P1Obs,
        rng: np.random.Generator | None = None,
    ) -> FilterSummary:
        """Advance one day given a masked ``RichObs`` (or legacy ``P1Obs``)."""
        if self._state is None:
            msg = "ResearchParticleFilter.initialize must be called before step"
            raise RuntimeError(msg)
        if rng is None:
            rng = spawn_rng(
                self._root_seed,
                run_id=self._run_id,
                day=self._day,
                stream=STREAM_FILTER_RESAMPLE,
            )
        rich = obs if isinstance(obs, RichObs) else RichObs.from_p1(obs)
        self._state = self._backend.predict_update(self._state, rich, self.params, rng)
        e = ess_fn(self._state.weights)
        log_lik = float(np.log(np.maximum(self._state.weights, 1e-300)).mean())
        self._day += 1
        return FilterSummary(ess=e, mean_L=float(self._state.L), log_lik=log_lik)

    def age_posterior(self, lot_index: int = 0) -> np.ndarray:
        if self._state is None:
            msg = (
                "ResearchParticleFilter.initialize must be called before age_posterior"
            )
            raise RuntimeError(msg)
        post = self._state.age_post[:, lot_index, :]
        w = self._state.weights[:, None]
        marg = (w * post).sum(axis=0)
        out = marg / max(float(marg.sum()), 1e-300)
        return cast("np.ndarray", out)


__all__ = ["ResearchParticleFilter"]
