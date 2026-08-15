"""Bakeoff-only counts RBPF update (research; not production hot path — ADR 0127)."""

from __future__ import annotations

import numpy as np

import blueberries_voi.filter.age_likelihood as age_likelihood
from blueberries_voi.filter.arrival_priors import delivery_birth_age_prior
from blueberries_voi.filter.particle.state import (
    ParticleState,
    _as_rich_obs,
    _observed_int,
    _systematic_resample,
    ess,
)
from blueberries_voi.filter.types import P1Obs, RichObs, age_grid
from blueberries_voi.model import (
    ModelParams,
    allocate_sales,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
)


def _rbpf_update_impl(
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
    """
    rich = _as_rich_obs(obs)
    n, L = state.counts.shape
    K = state.age_post.shape[-1]
    grid = age_grid(K)
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    days = state.days_on_shelf.astype(float) + 1.0
    # Arrival-age identity: advance calendar days only; keep prior mass.
    new_post = state.age_post.copy()

    ages_now = np.zeros((n, L), dtype=float)
    for ell in range(L):
        tau_now = grid + float(days[ell]) * dtau
        ages_now[:, ell] = (new_post[:, ell, :] * tau_now[None, :]).sum(axis=-1)

    sales_tot = _observed_int(rich.sales_total)
    waste_tot = _observed_int(rich.waste_total)
    # Default exact sequential WOR; multinomial is ablation-only (ADR 0105).
    if sales_likelihood == "multinomial":
        score_fn = age_likelihood.log_p_sales_waste_multinomial_given_ages
    else:
        score_fn = age_likelihood.log_p_sales_waste_given_ages

    log_like = np.zeros(n, dtype=float)
    for i in range(n):
        n_i = [int(x) for x in state.counts[i]]
        tau_i = [float(t) for t in ages_now[i]]
        if sales_tot is None and waste_tot is None:
            log_like[i] = 0.0
            continue
        if sales_tot is not None and waste_tot is not None:
            ll = float(score_fn(n_i, tau_i, sales_tot, waste_tot, params))
            log_like[i] = ll if np.isfinite(ll) else -1e300
            continue
        if sales_tot is not None:
            # P0 / waste UNOBSERVED: do not coerce waste=0. Under the
            # sales-total model (D = sales_tot), feasibility is age-free;
            # observed waste=0 still uses the full score_fn above.
            on_hand = int(sum(n_i))
            log_like[i] = 0.0 if 0 <= sales_tot <= on_hand else -1e300
            continue
        # waste observed, sales UNOBSERVED — leave flat (rare rung)
        log_like[i] = 0.0

    log_w = np.log(state.weights + 1e-300) + log_like
    log_w -= float(log_w.max())
    weights = np.exp(log_w)
    weights /= float(weights.sum())

    # Counts-only physics transition (not ±1 RW): allocate_sales then spoil.
    counts = np.zeros((n, L), dtype=int)
    for i in range(n):
        rem = np.asarray(state.counts[i], dtype=int).copy()
        tau = ages_now[i]
        on_hand = int(rem.sum())
        if on_hand <= 0:
            counts[i] = rem
            continue
        if sales_tot is not None:
            demand = int(sales_tot)
        else:
            demand = int(draw_demand(rng, params))
        w = picking_weights(
            [float(t) for t in tau],
            sigma=params.sigma,
            beta=params.beta,
            eta=params.eta_ref,
            uniform=params.uniform_picking,
        )
        sold = allocate_sales(rem.tolist(), demand, w, rng)
        rem = rem - np.asarray(sold, dtype=int)
        for ell in range(L):
            n_left = int(rem[ell])
            if n_left <= 0:
                rem[ell] = 0
                continue
            p_die = death_prob_survival_ratio(
                float(tau[ell]),
                float(dtau),
                beta=params.beta,
                eta=params.eta_ref,
            )
            waste = int(rng.binomial(n_left, float(p_die)))
            rem[ell] = n_left - waste
        counts[i] = np.maximum(rem, 0)

    arrivals_v = _observed_int(rich.arrivals)
    arrivals = 0 if arrivals_v is None else arrivals_v
    if arrivals > 0:
        counts = np.concatenate(
            [counts[:, 1:], np.full((n, 1), arrivals, dtype=int)],
            axis=1,
        )
        # Birth prior only (T-013): cold Abdella / F2a / F2 — not flat 1/K.
        birth = delivery_birth_age_prior(rich, grid, params)
        new_post = np.concatenate(
            [new_post[:, 1:, :], np.broadcast_to(birth, (n, 1, K)).copy()],
            axis=1,
        )
        days = np.concatenate([days[1:], np.asarray([0.0])])

    if ess(weights) < 0.5 * n:
        idx = _systematic_resample(weights, rng)
        counts = counts[idx]
        new_post = new_post[idx]
        weights = np.ones(n) / n

    return ParticleState(
        weights=weights,
        counts=counts,
        age_idx=state.age_idx,
        age_post=new_post,
        days_on_shelf=days,
        L=L,
        backend=backend_name,
    )
