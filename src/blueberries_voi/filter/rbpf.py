"""Production counts-only PF (ADR 0105): arrival-only ages + exact WOR weights."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import numpy as np  # needed for get_type_hints(RBPF.step)

from blueberries_voi.filter.backends import (
    CountsOnlyBackend,
    FilterBackend,
    ParticleState,
)
from blueberries_voi.filter.backends import (
    ess as ess_fn,
)
from blueberries_voi.filter.l_fallback import BackendChoice, choose_backend
from blueberries_voi.filter.types import (
    FilterSummary,
    P1Obs,
    RichObs,
    age_grid,
)
from blueberries_voi.model import ModelParams, day_step
from blueberries_voi.rng import STREAM_FILTER_RESAMPLE, spawn_rng

# Production numerics after ADR 0105 settle: counts-only arrival-age clock.
PRODUCTION_BACKEND: str = "counts_only"
PRODUCTION_K: int = 8
PRODUCTION_N: int = 2000
PRODUCTION_ESS_FRACTION: float = 0.5
# Measured L under M1 open-loop is ≤3; keep headroom for short spikes.
# Dynamic L (T-015): configured / empirical L is preferred; no joint gate.
PRODUCTION_L: int = 3


@dataclass
class RBPF:
    """Counts-only PF: sample counts; ages are arrival priors + MOD-02 clock."""

    params: ModelParams
    N: int = PRODUCTION_N
    K: int = PRODUCTION_K
    ess_fraction: float = PRODUCTION_ESS_FRACTION
    L: int = PRODUCTION_L
    sales_likelihood: str = "exact_sequential_wor"
    _backend: FilterBackend = field(default_factory=CountsOnlyBackend)
    _state: ParticleState | None = None
    _day: int = 0
    _root_seed: int = 0
    _run_id: str | int = "rbpf"
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
        # Re-evaluate when L changes (or on first init); stays counts_only.
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
        """Advance one day given a masked ``RichObs`` (or legacy ``P1Obs``).

        Production path scores present totals via exact sequential WOR
        (``log_p_sales_waste_given_ages``); ages advance by clock/birth only.
        """
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
        rich = obs if isinstance(obs, RichObs) else RichObs.from_p1(obs)
        self._state = self._backend.predict_update(self._state, rich, self.params, rng)
        e = ess_fn(self._state.weights)
        log_lik = float(np.log(np.maximum(self._state.weights, 1e-300)).mean())
        self._day += 1
        return FilterSummary(ess=e, mean_L=float(self._state.L), log_lik=log_lik)

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
    "BackendChoice",
    "FilterSummary",
    "P1Obs",
    "RichObs",
    "age_grid",
    "choose_backend",
    "day_step",
]
