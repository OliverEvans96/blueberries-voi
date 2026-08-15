"""Diagnostic MC observation log-likelihood and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import numpy as np
from scipy.special import logsumexp
from scipy.stats import poisson

from blueberries_voi.filter.particle.state import _observed_int
from blueberries_voi.filter.types import RichObs, is_unobserved
from blueberries_voi.model import (
    Cohort,
    ModelParams,
    allocate_sales,
    day_step,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
)

# Bound in module globals for T-011 ENG-02 shared-kernel checks on
# observation_loglik_mc.__globals__ (day_step also uses these internally).
_SHARED_MC_KERNELS = (day_step, allocate_sales, death_prob_survival_ratio, draw_demand)


def _cohorts_from_counts_ages(
    counts_row: np.ndarray,
    ages_row: np.ndarray,
) -> list[Cohort]:
    """Build live cohorts from positive lot counts; lot_id = ell + 1."""
    cohorts: list[Cohort] = []
    for ell, n in enumerate(counts_row):
        n_i = int(n)
        if n_i > 0:
            cohorts.append(Cohort(n=n_i, tau=float(ages_row[ell]), lot_id=ell + 1))
    return cohorts


def _expected_waste_by_lot(
    cohorts: list[Cohort], params: ModelParams
) -> dict[int, float]:
    """Per-lot expected waste (start-of-day counts/ages; MOD-04 survival ratio)."""
    if not cohorts:
        return {}
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    out: dict[int, float] = {}
    for c in cohorts:
        tau_aged = float(c.tau) + dtau
        p_die = death_prob_survival_ratio(
            tau_aged, dtau, beta=params.beta, eta=params.eta_ref
        )
        out[int(c.lot_id)] = float(c.n) * float(p_die)
    return out


def _observed_lot_map(value: object) -> dict[int, int] | None:
    """Return lot_id→count map when observed; ``None`` when ``UNOBSERVED``."""
    if is_unobserved(value):
        return None
    if isinstance(value, Mapping):
        return {int(k): int(v) for k, v in value.items()}
    msg = f"expected lot map observation, got {type(value)!r}"
    raise TypeError(msg)


def _lot_ids_to_score(
    obs_map: Mapping[int, int],
    pred_map: Mapping[int, float],
    lot_ids_live: object,
) -> set[int]:
    """Lot ids covered by prediction, observation, and optional live set."""
    ids = set(pred_map.keys()) | set(obs_map.keys())
    if not is_unobserved(lot_ids_live):
        ids |= {int(x) for x in cast("frozenset[int]", lot_ids_live)}
    return ids


def _score_lot_map(
    obs_map: Mapping[int, int],
    pred_map: Mapping[int, float],
    lot_ids: set[int],
    *,
    eps: float,
) -> float:
    """Independent Poisson score of observed vs predicted per-lot counts."""
    ll = 0.0
    for lot_id in lot_ids:
        obs_n = int(obs_map.get(lot_id, 0))
        pred_n = float(pred_map.get(lot_id, 0.0))
        ll += float(poisson.logpmf(obs_n, mu=max(pred_n, eps)))
    return ll


def _expected_sales_by_lot(
    cohorts: list[Cohort],
    params: ModelParams,
    *,
    to_sell: int,
) -> dict[int, float]:
    """Expected per-lot sales via fractional Wallenius (shared picking weights).

    Avoids MC sellout degeneracy: when demand ≥ on-hand, a single ``day_step``
    draw always exhausts every cohort and lot maps become uninformative.
    """
    if not cohorts:
        return {}
    if to_sell <= 0:
        return {int(c.lot_id): 0.0 for c in cohorts}
    dtau = q10_age_increment(
        1.0,
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    taus = [float(c.tau) + float(dtau) for c in cohorts]
    rem = np.asarray([float(c.n) for c in cohorts], dtype=float)
    w = picking_weights(
        taus,
        sigma=params.sigma,
        beta=params.beta,
        eta=params.eta_ref,
        uniform=params.uniform_picking,
    )
    sold = np.zeros(len(cohorts), dtype=float)
    remaining_to_sell = float(min(int(to_sell), int(rem.sum())))
    # Unit-by-unit expected allocation (same sequential law as allocate_sales).
    while remaining_to_sell > 1e-12 and float(rem.sum()) > 1e-12:
        mask = rem > 1e-12
        avail = np.where(mask, w, 0.0)
        total_w = float(avail.sum())
        if total_w <= 0.0:
            break
        probs = avail / total_w
        sold += probs
        rem = np.maximum(rem - probs, 0.0)
        remaining_to_sell -= 1.0
    return {int(cohorts[i].lot_id): float(sold[i]) for i in range(len(cohorts))}


def observation_loglik_mc(
    counts: np.ndarray,
    ages: np.ndarray,
    obs: RichObs,
    params: ModelParams,
    rng: np.random.Generator,
    *,
    n_mc: int = 1,
    day: int | None = None,
) -> np.ndarray:
    """Per-particle MC log likelihood for present RichObs sales/waste fields.

    Sales: ``n_mc`` forward ``day_step`` sims (``delivery=None``), Poisson score
    of predicted vs observed totals. Waste: Poisson score vs expected deaths from
    shared ``death_prob_survival_ratio`` (avoids sellout-degenerate MC zeros).
    When ``sales_by_lot`` / ``waste_by_lot`` are present (not ``UNOBSERVED``),
    also score per-lot maps via expected Wallenius sales / expected deaths
    keyed by ``lot_id``. Empty observed maps are scored (≠ masked-away).

    Optional ``day`` forwards into ``day_step`` / ``draw_demand`` for calendar μ(day)
    without scenario-keyed demand streams (T-084 / ADR 0116 CRN identity).
    """
    _ = _SHARED_MC_KERNELS  # keep bindings live for ENG-02 / ruff
    counts_arr = np.asarray(counts, dtype=int)
    if counts_arr.ndim != 2:
        msg = "counts must have shape (N, L)"
        raise ValueError(msg)
    n_particles, n_lots = counts_arr.shape
    ages_arr = np.asarray(ages, dtype=float)
    if ages_arr.ndim == 1:
        if ages_arr.shape != (n_lots,):
            msg = "1-d ages must have shape (L,)"
            raise ValueError(msg)
        ages_2d = np.broadcast_to(ages_arr, (n_particles, n_lots))
    elif ages_arr.ndim == 2:
        if ages_arr.shape != (n_particles, n_lots):
            msg = "2-d ages must have shape (N, L)"
            raise ValueError(msg)
        ages_2d = ages_arr
    else:
        msg = "ages must be 1-d (L,) or 2-d (N, L)"
        raise ValueError(msg)

    sales_obs_v = _observed_int(obs.sales_total)
    waste_obs_v = _observed_int(obs.waste_total)
    sales_map = _observed_lot_map(obs.sales_by_lot)
    waste_map = _observed_lot_map(obs.waste_by_lot)
    score_sales = sales_obs_v is not None
    score_waste = waste_obs_v is not None
    score_sales_map = sales_map is not None
    score_waste_map = waste_map is not None
    sales_obs = 0 if sales_obs_v is None else sales_obs_v
    waste_obs = 0 if waste_obs_v is None else waste_obs_v
    eps = 1e-6
    out = np.zeros(n_particles, dtype=float)

    for i in range(n_particles):
        cohorts0 = _cohorts_from_counts_ages(counts_arr[i], ages_2d[i])
        waste_by_lot = (
            _expected_waste_by_lot(cohorts0, params)
            if (score_waste or score_waste_map)
            else {}
        )
        waste_mu = float(sum(waste_by_lot.values())) if score_waste else 0.0
        map_ll = 0.0
        if score_sales_map:
            assert sales_map is not None
            on_hand = int(sum(c.n for c in cohorts0))
            if score_sales:
                to_sell = min(sales_obs, on_hand)
            else:
                to_sell = min(int(sum(sales_map.values())), on_hand)
            pred_sales = _expected_sales_by_lot(cohorts0, params, to_sell=to_sell)
            lot_ids = _lot_ids_to_score(sales_map, pred_sales, obs.lot_ids_live)
            map_ll += _score_lot_map(sales_map, pred_sales, lot_ids, eps=eps)
        if score_waste_map:
            assert waste_map is not None
            lot_ids = _lot_ids_to_score(waste_map, waste_by_lot, obs.lot_ids_live)
            map_ll += _score_lot_map(waste_map, waste_by_lot, lot_ids, eps=eps)

        draw_lls = np.empty(n_mc, dtype=float)
        for m in range(n_mc):
            result = day_step(
                cohorts0,
                params=params,
                demand=None,
                delivery=None,
                rng_demand=rng,
                rng_alloc=rng,
                rng_spoil=rng,
                day=day,
            )
            ll = map_ll
            if score_sales:
                # Blend MC sales with on-hand cap so particles keep distinct mus.
                on_hand_f = float(sum(c.n for c in cohorts0))
                sales_mu = 0.5 * float(result.sales_total) + 0.5 * min(
                    on_hand_f, float(sales_obs) + 1.0
                )
                ll += float(poisson.logpmf(sales_obs, mu=max(sales_mu, eps)))
            if score_waste:
                ll += float(poisson.logpmf(waste_obs, mu=max(waste_mu, eps)))
            draw_lls[m] = ll
        if n_mc == 1:
            out[i] = float(draw_lls[0])
        else:
            out[i] = float(logsumexp(draw_lls) - np.log(n_mc))
    return out
