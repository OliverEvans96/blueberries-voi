"""T-011 Honest MC observation likelihood (RED / acceptance)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import numpy as np

from blueberries_voi import filter as filter_pkg
from blueberries_voi import model
from blueberries_voi.filter import RBPF
from blueberries_voi.filter.types import (
    UNOBSERVED,
    FilterSummary,
    P1Obs,
    RichObs,
    mask_for,
)
from blueberries_voi.model import ModelParams

_SOFT_LL_SYMBOLS = frozenset({"sales_pow", "waste_pow", "sales_ll", "waste_ll"})
_WALLENIUS_DENSITY_MARKERS = (
    "wallenius_pmf",
    "wallenius_logpmf",
    "wallenius_density",
    "ncmhypergeom",
    "noncentral_hypergeometric",
    "multivariate_hypergeom",
    "dwallenius",
)


def _backends_source() -> str:
    import blueberries_voi.filter.backends as backends

    return Path(backends.__file__).read_text(encoding="utf-8")


def _rbpf_source() -> str:
    import blueberries_voi.filter.rbpf as rbpf_mod

    return Path(rbpf_mod.__file__).read_text(encoding="utf-8")


def _ast_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    msg = f"function {name!r} not found in source"
    raise AssertionError(msg)


def _names_in_function(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _resolve_observation_loglik_mc() -> Any:
    """Locate observation_loglik_mc without ImportError before asserts."""
    import blueberries_voi.filter.backends as backends

    found = getattr(backends, "observation_loglik_mc", None)
    if found is not None:
        return found
    return getattr(filter_pkg, "observation_loglik_mc", None)


def _full_rich(
    *,
    arrivals: int = 0,
    sales_total: int = 12,
    waste_total: int | object = 0,
) -> RichObs:
    return RichObs(
        arrivals=arrivals,
        sales_total=sales_total,
        waste_total=waste_total,  # type: ignore[arg-type]
        sales_by_lot=UNOBSERVED,
        waste_by_lot=UNOBSERVED,
        pack_date=UNOBSERVED,
        age_at_receipt=UNOBSERVED,
        lot_ids_live=UNOBSERVED,
    )


def _weights_after_one_step(obs: RichObs, *, seed: int = 0) -> np.ndarray:
    rbpf = RBPF(params=ModelParams(), N=40, K=4, L=2)
    rng = np.random.default_rng(seed)
    rbpf.initialize(rng)
    rbpf.step(obs, rng)
    assert rbpf._state is not None
    return np.asarray(rbpf._state.weights, dtype=float).copy()


def test_production_rbpf_update_has_no_soft_pow_or_gaussian_ll_symbols() -> None:
    """AC: production `_rbpf_update` must not use soft powers / Gaussian toy LL."""
    src = _backends_source()
    fn = _ast_function(src, "_rbpf_update")
    names = _names_in_function(fn)
    soft_present = sorted(names & _SOFT_LL_SYMBOLS)
    assert soft_present == [], (
        "production _rbpf_update still references soft-LL symbols: "
        f"{soft_present}; replace with observation_loglik_mc (ADR 0087)"
    )


def test_production_rbpf_update_does_not_default_to_observation_loglik_mc() -> None:
    """ADR 0105: MC LL remains for diagnostics; production weights are exact WOR."""
    src = _backends_source()
    fn = _ast_function(src, "_rbpf_update")
    names = _names_in_function(fn)
    assert "observation_loglik_mc" not in names, (
        "production _rbpf_update must not default to observation_loglik_mc (ADR 0105)"
    )
    wor = names & {
        "log_p_sales_waste_given_ages",
        "sequential_wor_pmf",
        "sequential_wor_composition_prob",
        "sequential_wor_composition_probs",
    }
    assert wor, "production particle weights must use exact sequential WOR"


def test_observation_loglik_mc_exists_with_n_mc_default_one() -> None:
    """AC: observation_loglik_mc exists; default MC draws n_mc=1."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, (
        "observation_loglik_mc must be defined (filter.backends or filter package)"
    )
    params = inspect.signature(fn).parameters
    assert "n_mc" in params, "observation_loglik_mc must expose n_mc"
    assert params["n_mc"].default == 1


def test_observation_loglik_mc_uses_shared_day_step_kernels() -> None:
    """AC: MC LL imports/calls shared allocate_sales / death / day_step (ENG-02)."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    g = fn.__globals__
    shared = (
        g.get("day_step") is model.day_step
        or g.get("allocate_sales") is model.allocate_sales
        or g.get("death_prob_survival_ratio") is model.death_prob_survival_ratio
        or g.get("draw_demand") is getattr(model, "draw_demand", object())
    )
    # Also accept identity via nested model module binding.
    model_mod = g.get("model")
    if model_mod is not None:
        shared = shared or (
            getattr(model_mod, "day_step", None) is model.day_step
            or getattr(model_mod, "allocate_sales", None) is model.allocate_sales
            or getattr(model_mod, "death_prob_survival_ratio", None)
            is model.death_prob_survival_ratio
        )
    assert shared, (
        "observation_loglik_mc must bind shared model.day_step / allocate_sales / "
        "death_prob_survival_ratio — not a forked spoilage formula"
    )


def test_observation_loglik_mc_returns_per_particle_loglik() -> None:
    """AC: observation_loglik_mc scores present fields → shape (N,)."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    n_particles, n_lots = 5, 2
    counts = np.full((n_particles, n_lots), 4, dtype=int)
    ages = np.linspace(1.0, 3.0, n_lots)
    obs = mask_for("P1").apply(_full_rich(waste_total=1))
    rng = np.random.default_rng(7)
    out = fn(counts, ages, obs, ModelParams(), rng, n_mc=1)
    assert isinstance(out, np.ndarray)
    assert out.shape == (n_particles,)


def test_unobserved_waste_not_scored_like_observed_zero() -> None:
    """AC: UNOBSERVED fields skipped — soft coerce-to-0 must not survive.

    Soft LL treated UNOBSERVED waste as 0, so UNOBSERVED and waste=0 produced
    identical weights. Honest MC must skip UNOBSERVED and score observed zero.
    """
    obs_unobs = _full_rich(waste_total=UNOBSERVED, sales_total=12, arrivals=0)
    obs_zero = _full_rich(waste_total=0, sales_total=12, arrivals=0)
    w_unobs = _weights_after_one_step(obs_unobs, seed=11)
    w_zero = _weights_after_one_step(obs_zero, seed=11)
    assert not np.allclose(w_unobs, w_zero), (
        "weights identical for waste=UNOBSERVED vs waste=0 — still soft-coerce "
        "conditioning; honest MC must skip UNOBSERVED waste"
    )


def test_p0_vs_p1_weight_divergence_when_waste_differs() -> None:
    """AC: P0 (waste masked) vs P1 (waste present) diverge when waste differs."""
    # Soft LL already diverges via coerce-to-0 vs waste=4; require soft gone first
    # so this locks honest masked scoring rather than the toy Gaussian path.
    update = _ast_function(_backends_source(), "_rbpf_update")
    soft_present = sorted(_names_in_function(update) & _SOFT_LL_SYMBOLS)
    assert soft_present == [], (
        "P0/P1 divergence under soft LL is not the acceptance gate; "
        f"remove soft symbols first: {soft_present}"
    )
    full = _full_rich(waste_total=4, sales_total=10, arrivals=2)
    obs_p0 = mask_for("P0").apply(full)
    obs_p1 = mask_for("P1").apply(full)
    assert obs_p0.waste_total is UNOBSERVED
    assert obs_p1.waste_total == 4
    w_p0 = _weights_after_one_step(obs_p0, seed=21)
    w_p1 = _weights_after_one_step(obs_p1, seed=21)
    assert not np.allclose(w_p0, w_p1), (
        "P0 and P1 weights identical despite differing waste presence — "
        "masked waste must not be coerced into the likelihood"
    )


def test_no_wallenius_density_in_production_filter_code() -> None:
    """AC: bootstrap simulates allocation; no Wallenius density in filter code."""
    sources = (_backends_source() + "\n" + _rbpf_source()).lower()
    hits = [m for m in _WALLENIUS_DENSITY_MARKERS if m in sources]
    assert hits == [], (
        f"Wallenius density markers in production filter code: {hits} "
        "(FIL-10=A: simulate allocate_sales only)"
    )


def test_filter_summary_exposes_ess() -> None:
    """AC: ESS available on FilterSummary so collapse is observable."""
    rbpf = RBPF(params=ModelParams(), N=30, K=4, L=2)
    rng = np.random.default_rng(3)
    rbpf.initialize(rng)
    summary = rbpf.step(RichObs.from_p1(P1Obs(12, 1, 8)), rng)
    assert isinstance(summary, FilterSummary)
    assert hasattr(summary, "ess")
    assert isinstance(summary.ess, float)
    assert summary.ess > 0.0


def test_filter_and_model_share_day_step_symbol() -> None:
    """AC / ENG-02: filter and sim resolve to the same day_step."""
    assert filter_pkg.day_step is model.day_step


def test_soft_ll_symbols_absent_from_production_update_path() -> None:
    """AC: soft Stage C tautology path — production update must not keep soft LL.

    Generative Stage C rewrite is T-012; T-011 locks soft symbols out of the
    production weight update so Stage C cannot stay a soft self-check.
    """
    src = _backends_source()
    update = _ast_function(src, "_rbpf_update")
    soft_in_update = sorted(_names_in_function(update) & _SOFT_LL_SYMBOLS)
    assert soft_in_update == [], (
        f"soft LL symbols still in _rbpf_update: {soft_in_update}"
    )
    # Bootstrap PF bakeoff path must not keep Gaussian sales_ll either if still
    # used as a production-facing weight update.
    boot = None
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "BootstrapPFBackend":
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == "predict_update"
                ):
                    boot = item
                    break
    assert boot is not None, "BootstrapPFBackend.predict_update missing"
    soft_boot = sorted(_names_in_function(boot) & _SOFT_LL_SYMBOLS)
    assert soft_boot == [], (
        f"soft LL symbols still in BootstrapPFBackend.predict_update: {soft_boot}"
    )


def test_observation_loglik_mc_skips_unobserved_fields_in_score() -> None:
    """AC: likelihood skips UNOBSERVED — direct MC LL P0 vs P1 divergence."""
    fn = _resolve_observation_loglik_mc()
    assert fn is not None, "observation_loglik_mc missing"
    n_particles, n_lots = 8, 2
    counts = np.full((n_particles, n_lots), 5, dtype=int)
    ages = np.asarray([1.5, 2.5], dtype=float)
    full = _full_rich(waste_total=3, sales_total=8, arrivals=1)
    obs_p0 = mask_for("P0").apply(full)
    obs_p1 = mask_for("P1").apply(full)
    rng0 = np.random.default_rng(99)
    rng1 = np.random.default_rng(99)
    ll_p0 = fn(counts, ages, obs_p0, ModelParams(), rng0, n_mc=1)
    ll_p1 = fn(counts, ages, obs_p1, ModelParams(), rng1, n_mc=1)
    assert ll_p0.shape == (n_particles,)
    assert ll_p1.shape == (n_particles,)
    assert not np.allclose(ll_p0, ll_p1), (
        "observation_loglik_mc identical for P0 vs P1 with waste=3 — "
        "UNOBSERVED waste must be skipped, not scored"
    )
