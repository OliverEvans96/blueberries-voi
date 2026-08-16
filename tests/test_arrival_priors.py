"""T-013 F2a pack-date prior + F2 age-at-receipt (RED / acceptance)."""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: ADR 0127 Wave F supersession — prod PF arrival priors removed",
    allow_module_level=True,
)

import ast
import inspect
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from typing import Any as ResearchParticleFilter  # T-121 F3

import numpy as np

from blueberries_voi import filter as filter_pkg
from blueberries_voi.filter.types import (
    UNOBSERVED,
    RichObs,
    age_grid,
    mask_for,
)
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments, shipment_arrival_age

# Documented F2 acceptance: ≥ this fraction of prior mass in the nearest grid bin(s).
# Spec leaves Dirac vs tiny-width open; either must meet this concentration floor.
F2_NEAREST_BIN_MASS_MIN = 0.95

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve(name: str) -> Any:
    """Locate a T-013 symbol without ImportError before asserts."""
    found = getattr(filter_pkg, name, None)
    if found is not None:
        return found
    try:
        import blueberries_voi.filter.backends as backends
    except ImportError:  # pragma: no cover
        return None
    return getattr(backends, name, None)


def _spread(weights: np.ndarray, grid: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    g = np.asarray(grid, dtype=float)
    w = w / max(float(w.sum()), 1e-300)
    mean = float(np.sum(g * w))
    var = float(np.sum(w * (g - mean) ** 2))
    return float(np.sqrt(max(var, 0.0)))


def _hpd_width(weights: np.ndarray, grid: np.ndarray, *, mass: float = 0.9) -> float:
    """Smallest contiguous grid span covering ``mass`` of the discrete prior."""
    w = np.asarray(weights, dtype=float)
    g = np.asarray(grid, dtype=float)
    w = w / max(float(w.sum()), 1e-300)
    k = len(w)
    best = float(g[-1] - g[0])
    for lo in range(k):
        cum = 0.0
        for hi in range(lo, k):
            cum += float(w[hi])
            if cum >= mass:
                best = min(best, float(g[hi] - g[lo]))
                break
    return best


def _cold_abdella_mix_prior(grid: np.ndarray, params: ModelParams) -> np.ndarray:
    """Oracle cold mix on ``grid`` (Abdella bootstrap histogram; test fixture only)."""
    ships = load_abdella_shipments(_REPO_ROOT / "data" / "abdella")
    ages = np.asarray(
        [
            shipment_arrival_age(s, q10=params.q10, t_ref_c=params.t_ref_c)
            for s in ships
        ],
        dtype=float,
    )
    g = np.asarray(grid, dtype=float)
    half = (g[1] - g[0]) / 2.0
    edges = np.concatenate([[g[0] - half], (g[:-1] + g[1:]) / 2.0, [g[-1] + half]])
    hist, _ = np.histogram(np.clip(ages, g[0], g[-1]), bins=edges)
    prior = hist.astype(float)
    return prior / max(float(prior.sum()), 1e-300)


def _call_f2a(
    fn: Any,
    pack_date: date,
    *,
    grid: np.ndarray,
    params: ModelParams,
    as_of: date,
) -> np.ndarray:
    """Call arrival_age_prior_f2a; accept optional as_of/receipt_date if present."""
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {"grid": grid, "params": params}
    if "as_of" in sig.parameters:
        kwargs["as_of"] = as_of
    elif "receipt_date" in sig.parameters:
        kwargs["receipt_date"] = as_of
    out = fn(pack_date, **kwargs)
    return np.asarray(out, dtype=float)


def _call_f2(fn: Any, age_at_receipt: float, *, grid: np.ndarray) -> np.ndarray:
    out = fn(age_at_receipt, grid=grid)
    return np.asarray(out, dtype=float)


def _full_rich(
    *,
    arrivals: int = 8,
    sales_total: int = 10,
    waste_total: int = 1,
    pack_date: date | object = UNOBSERVED,
    age_at_receipt: float | object = UNOBSERVED,
) -> RichObs:
    return RichObs(
        arrivals=arrivals,
        sales_total=sales_total,
        waste_total=waste_total,
        sales_by_lot=UNOBSERVED,
        waste_by_lot=UNOBSERVED,
        pack_date=pack_date,  # type: ignore[arg-type]
        age_at_receipt=age_at_receipt,  # type: ignore[arg-type]
        lot_ids_live=UNOBSERVED,
    )


def _new_lot_prior_after_step(
    obs: RichObs, *, seed: int = 0, K: int = 8, L: int = 3
) -> np.ndarray:
    """Marginal age prior on the newly injected delivery lot (last slot)."""
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=40, K=K, L=L)
    rng = np.random.default_rng(seed)
    particle_filter.initialize(rng)
    particle_filter.step(obs, rng)
    return np.asarray(particle_filter.age_posterior(L - 1), dtype=float)


def _weights_after_step(obs: RichObs, *, seed: int = 0) -> np.ndarray:
    particle_filter = ResearchParticleFilter(params=ModelParams(), N=40, K=4, L=2)
    rng = np.random.default_rng(seed)
    particle_filter.initialize(rng)
    particle_filter.step(obs, rng)
    assert particle_filter._state is not None
    return np.asarray(particle_filter._state.weights, dtype=float).copy()


def test_arrival_age_prior_f2a_exists_and_returns_normalized_weights() -> None:
    """AC interface: arrival_age_prior_f2a → length-K weights summing to 1."""
    fn = _resolve("arrival_age_prior_f2a")
    assert fn is not None, (
        "arrival_age_prior_f2a must be defined (filter package or backends)"
    )
    K = 8
    grid = age_grid(K)
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=4)
    prior = _call_f2a(fn, pack, grid=grid, params=ModelParams(), as_of=as_of)
    assert prior.shape == (K,)
    assert np.all(prior >= 0.0)
    assert abs(float(prior.sum()) - 1.0) < 1e-9


def test_f2a_prior_narrower_than_cold_abdella_mix() -> None:
    """AC: F2a-unmasked pack_date prior SD/HPD strictly < cold Abdella mix."""
    fn = _resolve("arrival_age_prior_f2a")
    assert fn is not None, "arrival_age_prior_f2a missing"
    params = ModelParams()
    K = 8
    grid = age_grid(K)
    cold = _cold_abdella_mix_prior(grid, params)
    as_of = date(2024, 3, 10)
    # Pack ~4 calendar days before receipt → transit band inside typical Abdella ages.
    pack = as_of - timedelta(days=4)
    f2a = _call_f2a(fn, pack, grid=grid, params=params, as_of=as_of)
    assert _spread(f2a, grid) < _spread(cold, grid), (
        "F2a prior SD must be strictly narrower than cold Abdella mix"
    )
    assert _hpd_width(f2a, grid) < _hpd_width(cold, grid), (
        "F2a 90% HPD width must be strictly narrower than cold Abdella mix"
    )


def test_arrival_age_prior_f2_exists_and_concentrates_on_measured_bin() -> None:
    """AC: F2 age_at_receipt → ≥ F2_NEAREST_BIN_MASS_MIN mass on nearest bin(s)."""
    fn = _resolve("arrival_age_prior_f2")
    assert fn is not None, (
        "arrival_age_prior_f2 must be defined (filter package or backends)"
    )
    K = 8
    grid = age_grid(K)
    tau = float(grid[3])  # exact grid centre
    prior = _call_f2(fn, tau, grid=grid)
    assert prior.shape == (K,)
    assert abs(float(prior.sum()) - 1.0) < 1e-9
    nearest = int(np.argmin(np.abs(grid - tau)))
    # Allow mass on nearest ±1 bin for documented tiny-width priors.
    mass = float(prior[max(0, nearest - 1) : nearest + 2].sum())
    assert mass >= F2_NEAREST_BIN_MASS_MIN, (
        f"F2 prior mass in nearest bin(s) is {mass:.4f}; "
        f"need ≥ {F2_NEAREST_BIN_MASS_MIN} (Dirac or tiny-width)"
    )


def test_f2_tighter_than_f2a_on_same_fixture() -> None:
    """AC: F2 concentrates more tightly than F2a when both apply conceptually."""
    f2a_fn = _resolve("arrival_age_prior_f2a")
    f2_fn = _resolve("arrival_age_prior_f2")
    assert f2a_fn is not None, "arrival_age_prior_f2a missing"
    assert f2_fn is not None, "arrival_age_prior_f2 missing"
    params = ModelParams()
    K = 8
    grid = age_grid(K)
    tau = 3.0
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=round(tau))
    f2a = _call_f2a(f2a_fn, pack, grid=grid, params=params, as_of=as_of)
    f2 = _call_f2(f2_fn, tau, grid=grid)
    assert _spread(f2, grid) < _spread(f2a, grid), (
        "F2 prior SD must be strictly tighter than F2a on the same age fixture"
    )


def test_p0_p1_delivery_prior_matches_cold_abdella_mix() -> None:
    """AC: under P0/P1 masks, delivery prior = baseline Abdella; F2a/F2 do not fire."""
    params = ModelParams()
    K = 8
    L = 3
    grid = age_grid(K)
    cold = _cold_abdella_mix_prior(grid, params)
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=4)
    # Concrete delivery metadata present on the raw RichObs, but masked away.
    full = _full_rich(
        arrivals=8,
        pack_date=pack,
        age_at_receipt=4.0,
    )
    for scenario in ("P0", "P1"):
        obs = mask_for(scenario).apply(full)
        assert obs.pack_date is UNOBSERVED
        assert obs.age_at_receipt is UNOBSERVED
        injected = _new_lot_prior_after_step(obs, seed=5, K=K, L=L)
        assert np.allclose(injected, cold, atol=1e-6), (
            f"{scenario} delivery prior must match cold Abdella mix "
            "(F2a/F2 paths must not fire when pack_date/age_at_receipt masked)"
        )


def test_f2a_mask_injects_narrower_new_lot_prior_than_p1() -> None:
    """AC: F2a-masked delivery day → new-cohort prior narrower than P1 baseline."""
    K = 8
    L = 3
    grid = age_grid(K)
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=4)
    full = _full_rich(arrivals=8, pack_date=pack, age_at_receipt=UNOBSERVED)
    obs_p1 = mask_for("P1").apply(full)
    obs_f2a = mask_for("F2a").apply(full)
    assert obs_f2a.pack_date == pack
    assert obs_p1.pack_date is UNOBSERVED
    prior_p1 = _new_lot_prior_after_step(obs_p1, seed=11, K=K, L=L)
    prior_f2a = _new_lot_prior_after_step(obs_f2a, seed=11, K=K, L=L)
    assert _spread(prior_f2a, grid) < _spread(prior_p1, grid), (
        "F2a new-lot age_post SD must be strictly < P1 (cold) delivery prior"
    )


def test_f2_mask_injects_concentrated_new_lot_prior() -> None:
    """AC: F2-masked delivery with age_at_receipt concentrates on measured bin."""
    K = 8
    L = 3
    grid = age_grid(K)
    tau = float(grid[2])
    # F2 mask requires lot maps / lot_ids present in schema.
    full = RichObs(
        arrivals=8,
        sales_total=10,
        waste_total=1,
        sales_by_lot={},
        waste_by_lot={},
        pack_date=UNOBSERVED,
        age_at_receipt=tau,
        lot_ids_live=frozenset(),
    )
    obs = mask_for("F2").apply(full)
    assert obs.age_at_receipt == tau
    prior = _new_lot_prior_after_step(obs, seed=13, K=K, L=L)
    nearest = int(np.argmin(np.abs(grid - tau)))
    mass = float(prior[max(0, nearest - 1) : nearest + 2].sum())
    assert mass >= F2_NEAREST_BIN_MASS_MIN, (
        f"F2 injected new-lot prior mass {mass:.4f} < {F2_NEAREST_BIN_MASS_MIN}"
    )


def test_sales_waste_weights_unchanged_when_only_prior_channel_differs() -> None:
    """AC: no new sales/waste soft terms — only birth prior / age_post changes.

    Same totals + arrivals; F2a vs P1 must share particle weights on the delivery
    day while differing on the new-lot age prior.
    """
    as_of = date(2024, 3, 10)
    pack = as_of - timedelta(days=4)
    full = _full_rich(arrivals=8, sales_total=12, waste_total=2, pack_date=pack)
    obs_p1 = mask_for("P1").apply(full)
    obs_f2a = mask_for("F2a").apply(full)
    w_p1 = _weights_after_step(obs_p1, seed=17)
    w_f2a = _weights_after_step(obs_f2a, seed=17)
    assert np.allclose(w_p1, w_f2a), (
        "particle weights diverged between P1 and F2a with identical sales/waste/"
        "arrivals — prior injection must not invent new soft sales/waste terms"
    )
    # And the prior channel must actually differ (else the AC is vacuous).
    K, L = 8, 3
    grid = age_grid(K)
    p1_prior = _new_lot_prior_after_step(obs_p1, seed=17, K=K, L=L)
    f2a_prior = _new_lot_prior_after_step(obs_f2a, seed=17, K=K, L=L)
    assert _spread(f2a_prior, grid) < _spread(p1_prior, grid), (
        "F2a must still narrow the new-lot prior while leaving weights unchanged"
    )


def test_no_new_soft_sales_waste_terms_tied_to_pack_or_receipt() -> None:
    """AC: sales/waste likelihood structure unchanged — no pack/receipt soft terms.

    Does not edit backends; only inspects that production update scoring does not
    bind pack_date / age_at_receipt into soft LL symbols.
    """
    import blueberries_voi.filter.backends as backends

    src = Path(backends.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    update = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            "_particle_filter_update",
            "observation_loglik_mc",
        }:
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            soft = names & {"sales_pow", "waste_pow", "sales_ll", "waste_ll"}
            prior_fields = names & {"pack_date", "age_at_receipt"}
            if soft and prior_fields:
                update = node.name
                break
    assert update is None, (
        f"{update} references pack_date/age_at_receipt together with soft sales/"
        "waste LL symbols — T-013 must only touch the birth-prior channel"
    )
