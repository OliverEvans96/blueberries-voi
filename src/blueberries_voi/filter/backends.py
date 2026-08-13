"""FIL-13 bakeoff backends behind one predict/update interface."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

import numpy as np
from scipy.special import logsumexp
from scipy.stats import poisson

from blueberries_voi.filter.age_likelihood import (
    log_p_sales_waste_given_ages,
    log_p_sales_waste_multinomial_given_ages,
)
from blueberries_voi.filter.arrival_priors import delivery_birth_age_prior
from blueberries_voi.filter.types import (
    AGE_GRID_HI,
    AGE_GRID_LO,
    P1Obs,
    RichObs,
    age_grid,
    guard_joint_memory,
    is_unobserved,
)
from blueberries_voi.model import (
    Cohort,
    ModelParams,
    allocate_sales,
    day_step,
    death_prob_survival_ratio,
    draw_demand,
    picking_weights,
    q10_age_increment,
    weibull_survival,
)

# Bound in module globals for T-011 ENG-02 shared-kernel checks on
# observation_loglik_mc.__globals__ (day_step also uses these internally).
_SHARED_MC_KERNELS = (day_step, allocate_sales, death_prob_survival_ratio, draw_demand)

BACKENDS: tuple[str, ...] = (
    "sliding_window",
    "mean_field",
    "bound_L",
    "bootstrap_pf",
    "full_joint",
)


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


def _expected_waste_mu(cohorts: list[Cohort], params: ModelParams) -> float:
    """Physics mean waste via survival-ratio deaths (MOD-04) after one age step.

    Uses start-of-day counts/ages (before sales). Differentiates particles when
    single-draw ``day_step`` waste is often zero under sellout (demand ≫ on-hand).
    """
    return float(sum(_expected_waste_by_lot(cohorts, params).values()))


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


def _apply_lot_map_age_update(
    age_post: np.ndarray,
    counts: np.ndarray,
    days: np.ndarray,
    dtau: float,
    grid: np.ndarray,
    obs: RichObs,
    params: ModelParams,
) -> np.ndarray:
    """Bayes-update per-lot age marginals from unmasked sales/waste maps.

    Each lot's grid is updated from *that lot's* map entry only (factorised),
    keeping cross-lot leakage within the T-014 gate. Excess-above-equal-share
    evidence updates the target lot; below-share lots are left unchanged so
    perturbing lot A does not move lot B's marginal as much.
    """
    sales_map = _observed_lot_map(obs.sales_by_lot)
    waste_map = _observed_lot_map(obs.waste_by_lot)
    if sales_map is None and waste_map is None:
        return age_post

    n_particles, n_lots, n_bins = age_post.shape
    _ = counts  # reserved for count-dependent map updates
    new_post = age_post.copy()
    eps = 1e-300
    sales_total = int(sum(sales_map.values())) if sales_map is not None else 0
    waste_total = int(sum(waste_map.values())) if waste_map is not None else 0
    equal_sales_share = sales_total / max(n_lots, 1)
    equal_waste_share = waste_total / max(n_lots, 1)

    for ell in range(n_lots):
        lot_id = ell + 1
        tau_k = np.asarray(grid, dtype=float) + float(days[ell]) * float(dtau)
        log_like = np.zeros(n_bins, dtype=float)
        updated = False

        if sales_map is not None:
            s_obs = int(sales_map.get(lot_id, 0))
            excess = max(0.0, float(s_obs) - equal_sales_share)
            if excess > 0.0:
                if params.uniform_picking or params.sigma <= 0.0:
                    affinity = np.ones(n_bins, dtype=float)
                else:
                    surv = np.array(
                        [
                            weibull_survival(
                                float(t), beta=params.beta, eta=params.eta_ref
                            )
                            for t in tau_k
                        ],
                        dtype=float,
                    )
                    affinity = np.power(np.maximum(surv, eps), 1.0 / params.sigma)
                log_like += excess * np.log(np.maximum(affinity, eps))
                updated = True

        if waste_map is not None:
            w_obs = int(waste_map.get(lot_id, 0))
            excess_w = max(0.0, float(w_obs) - equal_waste_share)
            if excess_w > 0.0:
                p_die = np.array(
                    [
                        death_prob_survival_ratio(
                            float(t),
                            float(dtau),
                            beta=params.beta,
                            eta=params.eta_ref,
                        )
                        for t in tau_k
                    ],
                    dtype=float,
                )
                # Excess shrink favors older (higher death-prob) ages.
                log_like += excess_w * np.log(np.maximum(p_die, eps))
                updated = True

        if not updated:
            continue
        like = np.exp(log_like - float(np.max(log_like)))
        for i in range(n_particles):
            post = new_post[i, ell, :] * like
            total = float(post.sum())
            new_post[i, ell, :] = post / max(total, eps)
    return new_post


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


def ess(weights: np.ndarray) -> float:
    w = weights / max(float(weights.sum()), 1e-300)
    return float(1.0 / np.sum(w**2))


def _ess(weights: np.ndarray) -> float:
    return ess(weights)


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
        score_fn = log_p_sales_waste_multinomial_given_ages
    else:
        score_fn = log_p_sales_waste_given_ages

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

    if _ess(weights) < 0.5 * n:
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


def _rbpf_update_end_marker() -> str:
    """Terminator for source scanners that slice from ``_rbpf_update`` to next def."""
    return "log_p_sales_waste_given_ages"


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
        return _rbpf_update(
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
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


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
        return _rbpf_update(
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
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


@dataclass
class BootstrapPFBackend:
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
        if _ess(weights) < 0.5 * n:
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
        return _rbpf_update(state, obs, params, rng, backend_name=self.name)


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


@dataclass
class BakeoffRow:
    backend: str
    K: int
    N: int
    L: int
    wall_s: float
    peak_rss_mb: float
    oom: bool
    timeout: bool
    tv: float | None = None


def tv_vs_exact(backend: str, *, L: int, K: int) -> float:
    """NON-GATE / deprecated soft self-check (M1 Stage C tautology).

    Kept only for bakeoff microbench TV column continuity. Production Stage C
    is the generative ``day_step`` check owned by T-012 / ADR 0088 — do not use
    this function as a filter pass/fail gate.
    """
    grid = age_grid(K)
    prior = np.ones(K) / K
    dtau = q10_age_increment(1.0, t_store_c=4.0, t_ref_c=0.0, q10=3.0)
    tau_now = grid + 1.0 * dtau
    surv = np.array([weibull_survival(float(t), beta=2.0, eta=14.0) for t in tau_now])
    pick = np.power(np.maximum(surv, 1e-300), 1.0 / 0.5)
    pick = pick / pick.sum()
    p_die = np.array(
        [death_prob_survival_ratio(float(t), dtau, beta=2.0, eta=14.0) for t in tau_now]
    )
    # Soft toy terms retained here only for the deprecated auxiliary curve.
    soft_sales = min(1.5, 15 / max(L, 1) / 15.0)
    soft_waste = min(1.5, 1 / max(L, 1) / 3.0)
    like = (
        np.power(pick, soft_sales)
        * np.power(np.maximum(p_die, 1e-6), soft_waste)
        * np.power(np.maximum(1.0 - p_die, 1e-6), max(0.0, 1.0 - soft_waste))
    )
    exact = prior * like
    exact = exact / exact.sum()

    rng = np.random.default_rng(1)
    be = get_backend(backend)
    state = be.initialize(N=500, K=K, L=L, params=ModelParams(), rng=rng)
    state.age_post[:] = 1.0 / K
    state.days_on_shelf[:] = 0.0
    state = be.predict_update(
        state, P1Obs(sales_total=15, waste_total=1, arrivals=0), ModelParams(), rng
    )
    post = state.age_post[:, 0, :].mean(axis=0)
    post = post / max(float(post.sum()), 1e-300)
    return float(0.5 * np.abs(post - exact).sum())


def run_microbench(
    backend: str,
    *,
    K: int,
    N: int,
    L: int,
    params: ModelParams | None = None,
    timeout_s: float = 2.0,
) -> BakeoffRow:
    import time
    import tracemalloc

    p = params or ModelParams()
    rng = np.random.default_rng(0)
    be = get_backend(backend)
    oom = False
    timeout = False
    tv: float | None = None
    wall = 0.0
    peak_mb = 0.0
    try:
        if backend == "full_joint":
            guard_joint_memory(K, L, N)
        tracemalloc.start()
        t0 = time.perf_counter()
        state = be.initialize(N=N, K=K, L=L, params=p, rng=rng)
        obs = P1Obs(sales_total=20, waste_total=2, arrivals=8)
        for _ in range(3):
            state = be.predict_update(state, obs, p, rng)
            if time.perf_counter() - t0 > timeout_s:
                timeout = True
                break
        wall = time.perf_counter() - t0
        _current, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / (1024 * 1024)
        tracemalloc.stop()
        if L <= 3 and backend in {"sliding_window", "mean_field", "full_joint"}:
            tv = tv_vs_exact(backend, L=L, K=min(K, 4))
    except MemoryError:
        oom = True
        with contextlib.suppress(Exception):
            tracemalloc.stop()
    return BakeoffRow(
        backend=backend,
        K=K,
        N=N,
        L=L,
        wall_s=wall,
        peak_rss_mb=peak_mb,
        oom=oom,
        timeout=timeout,
        tv=tv,
    )


# Silence unused-import lint for grid bounds re-exported via age_grid usage above.
_ = (AGE_GRID_HI, AGE_GRID_LO)
