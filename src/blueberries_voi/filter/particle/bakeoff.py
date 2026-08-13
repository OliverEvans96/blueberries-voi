"""Bakeoff / registry backends behind FilterBackend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blueberries_voi.filter.particle.counts_update import _rbpf_update_impl
from blueberries_voi.filter.particle.state import (
    FilterBackend,
    ParticleState,
    _new_state,
)
from blueberries_voi.filter.types import P1Obs, RichObs, guard_joint_memory

if TYPE_CHECKING:
    import numpy as np

    from blueberries_voi.model import ModelParams

BACKENDS: tuple[str, ...] = (
    "sliding_window",
    "mean_field",
    "bound_L",
    "bootstrap_pf",
    "full_joint",
)


@dataclass
class CountsOnlyBackend:
    """Production counts-only PF: arrival-only ages + exact WOR weights (ADR 0105)."""

    is_stub: bool = False
    name: str = "counts_only"
    sales_likelihood: str = "exact_sequential_wor"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update_impl(
            state,
            obs,
            params,
            rng,
            backend_name=self.name,
            sales_likelihood=self.sales_likelihood,
        )


@dataclass
class SlidingWindowBackend:
    """Non-production bakeoff stub — must not be cited as a production filter."""

    is_stub: bool = True
    name: str = "sliding_window"
    window: int = 3

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update_impl(state, obs, params, rng, backend_name=self.name)


@dataclass
class MeanFieldBackend:
    """Bakeoff registry arm B (name retained); uses counts-only ``_rbpf_update``.

    Production identity is ``CountsOnlyBackend`` / ``counts_only`` (ADR 0105).
    Diagnostic ``mean_field_update`` remains in ``age_likelihood`` only.
    """

    is_stub: bool = False
    name: str = "mean_field"
    sales_likelihood: str = "exact_sequential_wor"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        st = _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)
        return st

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update_impl(
            state,
            obs,
            params,
            rng,
            backend_name=self.name,
            sales_likelihood=self.sales_likelihood,
        )


@dataclass
class BoundLBackend:
    name: str = "bound_L"
    max_L: int = 4

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _new_state(N=N, K=K, L=min(L, self.max_L), rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        return _rbpf_update_impl(state, obs, params, rng, backend_name=self.name)


@dataclass
class FullJointBackend:
    """Non-production bakeoff stub — must not be cited as a production filter."""

    is_stub: bool = True
    name: str = "full_joint"

    def initialize(
        self,
        *,
        N: int,
        K: int,
        L: int,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        guard_joint_memory(K, L, N)
        return _new_state(N=N, K=K, L=L, rng=rng, backend=self.name)

    def predict_update(
        self,
        state: ParticleState,
        obs: RichObs | P1Obs,
        params: ModelParams,
        rng: np.random.Generator,
    ) -> ParticleState:
        guard_joint_memory(state.age_post.shape[-1], state.L, len(state.weights))
        return _rbpf_update_impl(state, obs, params, rng, backend_name=self.name)


def get_backend(name: str) -> FilterBackend:
    # Lazy import avoids cycle: backends façade owns BootstrapPFBackend (AST).
    from blueberries_voi.filter.backends import BootstrapPFBackend

    mapping: dict[str, FilterBackend] = {
        "counts_only": CountsOnlyBackend(),
        "sliding_window": SlidingWindowBackend(),
        "mean_field": MeanFieldBackend(),
        "bound_L": BoundLBackend(),
        "bootstrap_pf": BootstrapPFBackend(),
        "full_joint": FullJointBackend(),
    }
    if name not in mapping:
        msg = f"unknown backend {name!r}"
        raise ValueError(msg)
    return mapping[name]
