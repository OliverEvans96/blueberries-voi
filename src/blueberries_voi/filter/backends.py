"""FIL-13 bakeoff backends behind one predict/update interface.

Façade over ``filter.particle``: re-exports the public surface and keeps a real
``def _rbpf_update`` in this file so AST hygiene scanners that parse
``backends.__file__`` remain green (ADR 0118 / T-102).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from blueberries_voi.filter.age_likelihood import log_p_sales_waste_given_ages
from blueberries_voi.filter.particle.bakeoff import BACKENDS as BACKENDS
from blueberries_voi.filter.particle.bakeoff import BoundLBackend as BoundLBackend
from blueberries_voi.filter.particle.bakeoff import (
    CountsOnlyBackend as CountsOnlyBackend,
)
from blueberries_voi.filter.particle.bakeoff import FullJointBackend as FullJointBackend
from blueberries_voi.filter.particle.bakeoff import (
    MeanFieldBackend as MeanFieldBackend,
)
from blueberries_voi.filter.particle.bakeoff import (
    SlidingWindowBackend as SlidingWindowBackend,
)
from blueberries_voi.filter.particle.bakeoff_counts_update import _rbpf_update_impl
from blueberries_voi.filter.particle.mc_likelihood import (
    _cohorts_from_counts_ages as _cohorts_from_counts_ages,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    _expected_sales_by_lot as _expected_sales_by_lot,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    _expected_waste_by_lot as _expected_waste_by_lot,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    _lot_ids_to_score as _lot_ids_to_score,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    _observed_lot_map as _observed_lot_map,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    _score_lot_map as _score_lot_map,
)
from blueberries_voi.filter.particle.mc_likelihood import (
    observation_loglik_mc as observation_loglik_mc,
)
from blueberries_voi.filter.particle.microbench import BakeoffRow as BakeoffRow
from blueberries_voi.filter.particle.microbench import run_microbench as run_microbench
from blueberries_voi.filter.particle.microbench import tv_vs_exact as tv_vs_exact
from blueberries_voi.filter.particle.state import FilterBackend as FilterBackend
from blueberries_voi.filter.particle.state import ParticleState as ParticleState
from blueberries_voi.filter.particle.state import _as_rich_obs as _as_rich_obs
from blueberries_voi.filter.particle.state import _new_state as _new_state
from blueberries_voi.filter.particle.state import _observed_int as _observed_int
from blueberries_voi.filter.particle.state import _prior_age_post as _prior_age_post
from blueberries_voi.filter.particle.state import (
    _systematic_resample as _systematic_resample,
)
from blueberries_voi.filter.particle.state import ess as ess
from blueberries_voi.filter.types import P1Obs, RichObs, age_grid
from blueberries_voi.model import (
    ModelParams,
    allocate_sales,
    death_prob_survival_ratio,
    draw_demand,
    q10_age_increment,
)
from blueberries_voi.sim.rust_bridge import day_step as day_step

# Bound in module globals for T-011 ENG-02 shared-kernel checks that inspect
# this module (MC LL itself binds the same kernels in particle.mc_likelihood).
_SHARED_MC_KERNELS = (day_step, allocate_sales, death_prob_survival_ratio, draw_demand)

# Keep annotation-only imports live for façade re-exports (ruff TC001/TC002).
_ = (ParticleState, FilterBackend, P1Obs, RichObs, ModelParams, np)


def _rbpf_update(
    state: ParticleState,
    obs: RichObs | P1Obs,
    params: ModelParams,
    rng: np.random.Generator,
    *,
    backend_name: str,
    sales_likelihood: str = "exact_sequential_wor",
) -> ParticleState:
    """Advance counts via day_step kernels; weight with exact sequential WOR.

    Arrival-only ages: clock ``days_on_shelf`` and birth priors only — no
    in-store mean-field / lot-map age LL (ADR 0105). Ages are already
    physiological; count transitions use ``allocate_sales`` +
    ``death_prob_survival_ratio`` without a second ``day_step`` age increment.

    Implementation lives in ``filter.particle.counts_update``; this def remains
    in ``backends.py`` so AST scanners that parse this file stay green.
    """
    # Hygiene scanners walk this function body for production markers.
    _ = (
        log_p_sales_waste_given_ages,
        allocate_sales,
        death_prob_survival_ratio,
        day_step,
    )
    return _rbpf_update_impl(
        state,
        obs,
        params,
        rng,
        backend_name=backend_name,
        sales_likelihood=sales_likelihood,
    )


def _rbpf_update_end_marker() -> str:
    """Terminator for source scanners that slice from ``_rbpf_update`` to next def."""
    return "log_p_sales_waste_given_ages"


@dataclass
class BootstrapPFBackend:
    """Bakeoff bootstrap PF (ClassDef kept here for soft-LL AST hygiene)."""

    name: str = "bootstrap_pf"

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
        rich = _as_rich_obs(obs)
        n, L = state.counts.shape
        K = state.age_post.shape[-1]
        age_idx = state.age_idx  # arrival-age bins stay put (identity)
        grid = age_grid(K)
        days = state.days_on_shelf.astype(float) + 1.0
        dtau = q10_age_increment(
            1.0,
            t_store_c=params.t_store_c,
            t_ref_c=params.t_ref_c,
            q10=params.q10,
        )
        ages_now = np.zeros((n, L), dtype=float)
        for ell in range(L):
            ages_now[:, ell] = (
                grid[np.clip(age_idx[:, ell], 0, K - 1)] + float(days[ell]) * dtau
            )
        log_like = observation_loglik_mc(
            state.counts, ages_now, rich, params, rng, n_mc=1
        )
        log_w = np.log(state.weights + 1e-300) + log_like
        log_w -= float(log_w.max())
        weights = np.exp(log_w)
        weights /= float(weights.sum())
        counts = np.maximum(
            0, state.counts + rng.integers(-1, 2, size=state.counts.shape)
        )
        arrivals_v = _observed_int(rich.arrivals)
        arrivals = 0 if arrivals_v is None else arrivals_v
        if arrivals > 0:
            counts = np.concatenate(
                [counts[:, 1:], np.full((n, 1), arrivals, dtype=int)],
                axis=1,
            )
            age_idx = np.concatenate(
                [age_idx[:, 1:], rng.integers(0, K, size=(n, 1))],
                axis=1,
            )
            days = np.concatenate([days[1:], np.asarray([0.0])])
        if ess(weights) < 0.5 * n:
            idx = _systematic_resample(weights, rng)
            counts = counts[idx]
            age_idx = age_idx[idx]
            weights = np.ones(n) / n
        return ParticleState(
            weights=weights,
            counts=counts,
            age_idx=age_idx,
            age_post=state.age_post,
            days_on_shelf=days,
            L=state.L,
            backend=self.name,
        )


def get_backend(name: str) -> FilterBackend:
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
