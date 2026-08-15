"""T-014 F1/F1s lot-resolved likelihood (RED / acceptance)."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: ADR 0127 Wave F supersession — prod PF lot-resolved LL removed",
    allow_module_level=True,
)

import inspect
from pathlib import Path
from typing import Any
from typing import Any as ResearchParticleFilter  # T-121 F3

import numpy as np

from blueberries_voi import filter as filter_pkg
from blueberries_voi.filter.types import (
    UNOBSERVED,
    RichObs,
    is_unobserved,
    mask_for,
    rich_obs_from_day_log,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.sim import run_episode

# Cross-lot leakage: |Δ other-lot marginal| / |Δ target-lot marginal| must stay
# below this bound when only the target lot's map entry is perturbed (plan §3.2 /
# T-014 open question — numeric threshold locked here for the gate).
CROSS_LOT_LEAKAGE_BOUND = 0.5
_MIN_TARGET_DELTA = 1e-4


def _resolve_observation_loglik_mc() -> Any:
    """Locate observation_loglik_mc without ImportError before asserts."""
    import blueberries_voi.filter.backends as backends

    found = getattr(backends, "observation_loglik_mc", None)
    if found is not None:
        return found
    return getattr(filter_pkg, "observation_loglik_mc", None)


def _rich(
    *,
    arrivals: int = 0,
    sales_total: int = 10,
    waste_total: int | object = 0,
    sales_by_lot: object = UNOBSERVED,
    waste_by_lot: object = UNOBSERVED,
    lot_ids_live: object = frozenset({1, 2}),
) -> RichObs:
    return RichObs(
        arrivals=arrivals,
        sales_total=sales_total,
        waste_total=waste_total,  # type: ignore[arg-type]
        sales_by_lot=sales_by_lot,  # type: ignore[arg-type]
        waste_by_lot=waste_by_lot,  # type: ignore[arg-type]
        pack_date=UNOBSERVED,
        age_at_receipt=UNOBSERVED,
        lot_ids_live=lot_ids_live,  # type: ignore[arg-type]
    )


def _l1(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).sum())


def _weighted_count_mean(counts: np.ndarray, loglik: np.ndarray) -> np.ndarray:
    """Importance-weighted mean lot counts from MC LL (count posterior proxy)."""
    ll = np.asarray(loglik, dtype=float)
    w = np.exp(ll - np.max(ll))
    w = w / max(float(w.sum()), 1e-300)
    mean = (w[:, None] * np.asarray(counts, dtype=float)).sum(axis=0)
    return np.asarray(mean, dtype=float)


def _age_posts_after_step(obs: RichObs, *, seed: int) -> tuple[np.ndarray, np.ndarray]:
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=80, K=4, L=2)
    rng = np.random.default_rng(seed)
    particle_filter.initialize(rng)
    # Fixed inventory so map terms (not random init) drive the update.
    assert particle_filter._state is not None
    particle_filter._state.counts[:] = np.asarray(
        [[8, 8]] * particle_filter.N, dtype=int
    )
    particle_filter.step(obs, rng)
    return particle_filter.age_posterior(0), particle_filter.age_posterior(1)


# ---------------------------------------------------------------------------
# AC: sales_by_lot present → per-lot sales scored; cross-lot leakage bound
# ---------------------------------------------------------------------------


def test_observation_loglik_mc_scores_sales_by_lot_when_present() -> None:
    """AC: F1/F2 sales_by_lot changes LL even when sales_total is fixed."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing (T-011 prerequisite)"
    n_particles, n_lots = 12, 2
    # Asymmetric ages so lot attribution is informative under Wallenius/picking.
    counts = np.full((n_particles, n_lots), 6, dtype=int)
    ages = np.asarray([1.0, 4.0], dtype=float)
    base = mask_for("F1").apply(
        _rich(
            sales_total=10,
            waste_total=0,
            sales_by_lot={1: 10, 2: 0},
            waste_by_lot=UNOBSERVED,
        )
    )
    swapped = mask_for("F1").apply(
        _rich(
            sales_total=10,
            waste_total=0,
            sales_by_lot={1: 0, 2: 10},
            waste_by_lot=UNOBSERVED,
        )
    )
    assert not is_unobserved(base.sales_by_lot)
    assert not is_unobserved(swapped.sales_by_lot)
    rng0 = np.random.default_rng(41)
    rng1 = np.random.default_rng(41)
    ll_base = fn(counts, ages, base, ModelParams(), rng0, n_mc=1)
    ll_swapped = fn(counts, ages, swapped, ModelParams(), rng1, n_mc=1)
    assert ll_base.shape == (n_particles,)
    assert not np.allclose(ll_base, ll_swapped), (
        "sales_by_lot ignored — LL identical for {1:10,2:0} vs {1:0,2:10} "
        "with fixed sales_total (T-014 must score per-lot sales)"
    )


def test_sales_by_lot_update_targets_lot_a_more_than_lot_b_leakage_bound() -> None:
    """AC: updating lot A sales moves lot A age/count posterior more than lot B.

    Leakage metric: L1 change in lot-B age posterior / L1 change in lot-A
    age posterior ≤ CROSS_LOT_LEAKAGE_BOUND after perturbing only lot A's
    sales_by_lot entry (sales_total held fixed).
    """
    baseline = mask_for("F1").apply(
        _rich(
            sales_total=12,
            waste_total=0,
            sales_by_lot={1: 6, 2: 6},
            waste_by_lot=UNOBSERVED,
        )
    )
    # Perturb only lot A (lot_id 1 → lot_index 0); lot B stays at 2 units sold.
    perturbed = mask_for("F1").apply(
        _rich(
            sales_total=12,
            waste_total=0,
            sales_by_lot={1: 10, 2: 2},
            waste_by_lot=UNOBSERVED,
        )
    )
    post_a0, post_b0 = _age_posts_after_step(baseline, seed=17)
    post_a1, post_b1 = _age_posts_after_step(perturbed, seed=17)
    delta_a = _l1(post_a0, post_a1)
    delta_b = _l1(post_b0, post_b1)
    # ADR 0105 / T-068: arrival-only ages — lot maps must not rewrite age_post.
    assert delta_a <= 1e-9, (
        f"lot-A age posterior moved Δ={delta_a:.4g} under sales_by_lot — "
        "in-store lot-map age LL must not run (ADR 0105)"
    )
    assert delta_b <= 1e-9, (
        f"lot-B age posterior moved Δ={delta_b:.4g} under sales_by_lot — "
        "in-store lot-map age LL must not run (ADR 0105)"
    )


def test_sales_by_lot_shifts_count_posterior_toward_observed_lot() -> None:
    """AC: count-posterior proxy — sales attributed to lot A reweights that lot."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    # Particles differ only in which lot holds stock.
    counts = np.asarray(
        [
            [10, 2],
            [10, 2],
            [2, 10],
            [2, 10],
        ],
        dtype=int,
    )
    ages = np.asarray([2.0, 2.0], dtype=float)
    obs_a = mask_for("F1").apply(
        _rich(
            sales_total=8,
            waste_total=0,
            sales_by_lot={1: 8, 2: 0},
            waste_by_lot=UNOBSERVED,
        )
    )
    obs_b = mask_for("F1").apply(
        _rich(
            sales_total=8,
            waste_total=0,
            sales_by_lot={1: 0, 2: 8},
            waste_by_lot=UNOBSERVED,
        )
    )
    rng_a = np.random.default_rng(3)
    rng_b = np.random.default_rng(3)
    mean_a = _weighted_count_mean(
        counts, fn(counts, ages, obs_a, ModelParams(), rng_a, n_mc=1)
    )
    mean_b = _weighted_count_mean(
        counts, fn(counts, ages, obs_b, ModelParams(), rng_b, n_mc=1)
    )
    # Observing sales from lot A should prefer high count on lot A more than
    # observing sales from lot B.
    assert mean_a[0] - mean_a[1] > mean_b[0] - mean_b[1] + _MIN_TARGET_DELTA, (
        "sales_by_lot did not shift count posterior toward the observed lot "
        f"(mean_a={mean_a}, mean_b={mean_b})"
    )


# ---------------------------------------------------------------------------
# AC: waste_by_lot present → per-lot waste scored; leakage analogous
# ---------------------------------------------------------------------------


def test_observation_loglik_mc_scores_waste_by_lot_when_present() -> None:
    """AC: F1s/F2 waste_by_lot changes LL even when waste_total is fixed."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing (T-011 prerequisite)"
    n_particles, n_lots = 12, 2
    counts = np.full((n_particles, n_lots), 6, dtype=int)
    ages = np.asarray([1.0, 4.0], dtype=float)
    base = mask_for("F1s").apply(
        _rich(
            sales_total=4,
            waste_total=3,
            sales_by_lot=UNOBSERVED,
            waste_by_lot={1: 3, 2: 0},
        )
    )
    swapped = mask_for("F1s").apply(
        _rich(
            sales_total=4,
            waste_total=3,
            sales_by_lot=UNOBSERVED,
            waste_by_lot={1: 0, 2: 3},
        )
    )
    assert not is_unobserved(base.waste_by_lot)
    assert not is_unobserved(swapped.waste_by_lot)
    rng0 = np.random.default_rng(42)
    rng1 = np.random.default_rng(42)
    ll_base = fn(counts, ages, base, ModelParams(), rng0, n_mc=1)
    ll_swapped = fn(counts, ages, swapped, ModelParams(), rng1, n_mc=1)
    assert ll_base.shape == (n_particles,)
    assert not np.allclose(ll_base, ll_swapped), (
        "waste_by_lot ignored — LL identical for {1:3,2:0} vs {1:0,2:3} "
        "with fixed waste_total (T-014 must score per-lot waste)"
    )


def test_waste_by_lot_update_targets_lot_a_more_than_lot_b_leakage_bound() -> None:
    """AC: updating lot A waste moves lot A age posterior more than lot B."""
    baseline = mask_for("F1s").apply(
        _rich(
            sales_total=4,
            waste_total=4,
            sales_by_lot=UNOBSERVED,
            waste_by_lot={1: 2, 2: 2},
        )
    )
    perturbed = mask_for("F1s").apply(
        _rich(
            sales_total=4,
            waste_total=4,
            sales_by_lot=UNOBSERVED,
            waste_by_lot={1: 4, 2: 0},
        )
    )
    post_a0, post_b0 = _age_posts_after_step(baseline, seed=19)
    post_a1, post_b1 = _age_posts_after_step(perturbed, seed=19)
    delta_a = _l1(post_a0, post_a1)
    delta_b = _l1(post_b0, post_b1)
    # ADR 0105 / T-068: arrival-only ages — lot maps must not rewrite age_post.
    assert delta_a <= 1e-9, (
        f"lot-A age posterior moved Δ={delta_a:.4g} under waste_by_lot — "
        "in-store lot-map age LL must not run (ADR 0105)"
    )
    assert delta_b <= 1e-9, (
        f"lot-B age posterior moved Δ={delta_b:.4g} under waste_by_lot — "
        "in-store lot-map age LL must not run (ADR 0105)"
    )


# ---------------------------------------------------------------------------
# AC: UNOBSERVED maps → totals-only; empty map ≠ UNOBSERVED
# ---------------------------------------------------------------------------


def test_unobserved_lot_maps_match_totals_only_scoring() -> None:
    """AC: P0/P1 UNOBSERVED maps do not change LL vs totals-only RichObs."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    counts = np.full((8, 2), 5, dtype=int)
    ages = np.asarray([1.5, 2.5], dtype=float)
    totals_only = _rich(
        sales_total=8,
        waste_total=2,
        sales_by_lot=UNOBSERVED,
        waste_by_lot=UNOBSERVED,
        lot_ids_live=UNOBSERVED,
    )
    # Masked P1 still has UNOBSERVED maps even if the pre-mask maps differed.
    p1_from_maps = mask_for("P1").apply(
        _rich(
            sales_total=8,
            waste_total=2,
            sales_by_lot={1: 99, 2: 0},
            waste_by_lot={1: 0, 2: 99},
        )
    )
    assert is_unobserved(p1_from_maps.sales_by_lot)
    assert is_unobserved(p1_from_maps.waste_by_lot)
    rng0 = np.random.default_rng(7)
    rng1 = np.random.default_rng(7)
    ll_totals = fn(counts, ages, totals_only, ModelParams(), rng0, n_mc=1)
    ll_p1 = fn(counts, ages, p1_from_maps, ModelParams(), rng1, n_mc=1)
    assert np.allclose(ll_totals, ll_p1), (
        "P1 UNOBSERVED lot maps diverged from totals-only scoring — "
        "masked maps must not condition the LL"
    )


def test_empty_observed_sales_by_lot_not_scored_like_unobserved() -> None:
    """AC: no accidental empty-map conditioning — {} ≠ UNOBSERVED."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    counts = np.full((8, 2), 5, dtype=int)
    ages = np.asarray([1.5, 2.5], dtype=float)
    # Positive totals + observed empty map is informative once lot terms exist;
    # UNOBSERVED must skip the map (totals-only), not treat it as {}.
    obs_empty = _rich(
        sales_total=10,
        waste_total=UNOBSERVED,
        sales_by_lot={},
        waste_by_lot=UNOBSERVED,
        lot_ids_live=frozenset({1, 2}),
    )
    obs_unobs = _rich(
        sales_total=10,
        waste_total=UNOBSERVED,
        sales_by_lot=UNOBSERVED,
        waste_by_lot=UNOBSERVED,
        lot_ids_live=frozenset({1, 2}),
    )
    assert obs_empty.sales_by_lot == {}
    assert not is_unobserved(obs_empty.sales_by_lot)
    assert is_unobserved(obs_unobs.sales_by_lot)
    rng0 = np.random.default_rng(11)
    rng1 = np.random.default_rng(11)
    ll_empty = fn(counts, ages, obs_empty, ModelParams(), rng0, n_mc=1)
    ll_unobs = fn(counts, ages, obs_unobs, ModelParams(), rng1, n_mc=1)
    assert not np.allclose(ll_empty, ll_unobs), (
        "observed sales_by_lot={} scored identically to UNOBSERVED — "
        "empty map must not be treated as masked-away (no empty-map conditioning)"
    )


# ---------------------------------------------------------------------------
# AC: F1 default rho=1 complete DayLog maps; biased-rho not a gate
# ---------------------------------------------------------------------------


def test_f1_default_rho_one_sales_by_lot_complete_for_sold_lots() -> None:
    """AC: rho=1 — DayLog sales_by_lot complete; F1 projects the full map."""
    log = run_episode(
        ModelParams(),
        root_seed=5,
        run_id="t014-rho",
        n_burn=2,
        n_score=10,
    )
    for day in log.days:
        assert day.sales_total == sum(day.sales_by_lot.values())
        if day.sales_total > 0:
            assert day.sales_by_lot, "sold day must attribute units to lot ids (rho=1)"
        f1 = rich_obs_from_day_log(day, mask_for("F1"))
        assert f1.sales_by_lot == day.sales_by_lot
        assert not is_unobserved(f1.sales_by_lot)


def test_biased_rho_sampler_absent_or_marked_non_gate() -> None:
    """AC: biased early-adopter rho<1 is not a production DoD/gate path."""
    root = Path(__file__).resolve().parents[1] / "src" / "blueberries_voi"
    gate_markers = (
        "biased_rho",
        "sample_rho",
        "rho_bias",
        "early_adopter_rho",
        "thin_sales_by_lot",
    )
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in gate_markers:
            if marker in text:
                hits.append(f"{path.relative_to(root)}:{marker}")
    assert hits == [], (
        "biased-rho sampler markers in package sources — must be absent or "
        f"moved behind a clearly marked non-gate sensitivity helper: {hits}"
    )


# ---------------------------------------------------------------------------
# AC: one particle filter class / one MC LL entrypoint
# ---------------------------------------------------------------------------


def test_single_particle_filter_class_and_one_mc_ll_entrypoint() -> None:
    """AC: no rung-specific PF subclass; shared observation_loglik_mc only."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    assert inspect.isfunction(fn)
    # No F1/F1s specialised particle filters.
    assert ResearchParticleFilter.__subclasses__() == [], (
        f"rung-specific PF subclasses not allowed: {RPF.__subclasses__()}"
    )
    filter_src = Path(filter_pkg.__file__).resolve().parent
    banned = (
        "F1ParticleFilter",
        "F1sParticleFilter",
        "LotResolvedParticleFilter",
        "ScenarioParticleFilter",
    )
    found: list[str] = []
    for path in filter_src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in banned:
            if name in text:
                found.append(f"{path.name}:{name}")
    assert found == [], f"rung-specific filter types in filter package: {found}"
