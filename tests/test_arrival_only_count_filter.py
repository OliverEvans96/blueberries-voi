"""T-068 / ADR 0105: arrival-only ages, counts-only PF, exact WOR weights (RED)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import Any

import numpy as np
import pytest  # noqa: TC002

from blueberries_voi.filter import RBPF
from blueberries_voi.filter.types import UNOBSERVED, RichObs, mask_for
from blueberries_voi.model import ModelParams

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SIMPLEX_TOL = 1e-6
_TV_TOL = 1e-9


def _backends_source() -> str:
    import blueberries_voi.filter.backends as backends

    return Path(backends.__file__).read_text(encoding="utf-8")


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


def _attr_names_in_function(fn: ast.AST) -> set[str]:
    return {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}


def _p1_unobserved_maps(
    *,
    sales_total: int = 10,
    waste_total: int = 2,
    arrivals: int = 0,
) -> RichObs:
    """P1 totals observed; lot maps UNOBSERVED."""
    return mask_for("P1").apply(
        RichObs(
            arrivals=arrivals,
            sales_total=sales_total,
            waste_total=waste_total,
            sales_by_lot={1: sales_total, 2: 0},
            waste_by_lot={1: waste_total, 2: 0},
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )
    )


def _lot_tv(a: np.ndarray, b: np.ndarray) -> float:
    return 0.5 * float(
        np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).sum()
    )


def _has_pm1_count_rw(fn: ast.AST) -> bool:
    """True if body contains rng.integers(-1, 2, ...) ±1 count random walk."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_integers = (isinstance(func, ast.Attribute) and func.attr == "integers") or (
            isinstance(func, ast.Name) and func.id == "integers"
        )
        if not is_integers:
            continue
        if len(node.args) >= 2:
            lo, hi = node.args[0], node.args[1]
            if (
                isinstance(lo, ast.UnaryOp)
                and isinstance(lo.op, ast.USub)
                and isinstance(lo.operand, ast.Constant)
                and lo.operand.value == 1
                and isinstance(hi, ast.Constant)
                and hi.value == 2
            ):
                return True
            if (
                isinstance(lo, ast.Constant)
                and lo.value == -1
                and isinstance(hi, ast.Constant)
                and hi.value == 2
            ):
                return True
    return False


# ---------------------------------------------------------------------------
# AC: no production path calls mean_field_update
# ---------------------------------------------------------------------------


def test_rbpf_update_source_does_not_call_mean_field_update() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    assert "mean_field_update" not in names, (
        "ADR 0105: production _rbpf_update must not call mean_field_update"
    )


def test_p1_unobserved_maps_does_not_invoke_mean_field_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "mean_field_update", _spy)
    if hasattr(backends, "mean_field_update"):
        monkeypatch.setattr(backends, "mean_field_update", _spy)

    rbpf = RBPF(params=ModelParams(), N=24, K=4, L=2)
    rng = np.random.default_rng(11)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[6, 6]] * rbpf.N, dtype=int)
    obs = _p1_unobserved_maps(sales_total=8, waste_total=2)
    assert obs.sales_by_lot is UNOBSERVED
    rbpf.step(obs, rng)
    assert not calls, (
        "mean_field_update must not run on production P1 UNOBSERVED-maps step "
        "(ADR 0105 arrival-only ages)"
    )


def test_thin_callers_do_not_name_mean_field_update() -> None:
    """Closed-loop thin callers must not invoke mean_field_update directly."""
    rels = (
        "src/blueberries_voi/simulator/day_driver.py",
        "src/blueberries_voi/sim/m2_multi_scenario.py",
        "src/blueberries_voi/voi/crn.py",
    )
    for rel in rels:
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "mean_field_update" not in text, (
            f"{rel} must not reference mean_field_update (ADR 0105)"
        )


# ---------------------------------------------------------------------------
# AC: default weights = exact sequential WOR
# ---------------------------------------------------------------------------


def test_rbpf_update_weights_use_exact_wor_not_mc_default() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    wor_markers = names & {
        "log_p_sales_waste_given_ages",
        "sequential_wor_pmf",
        "sequential_wor_composition_prob",
        "sequential_wor_composition_probs",
    }
    assert wor_markers, (
        "production _rbpf_update must weight particles with exact sequential WOR "
        "(log_p_sales_waste_given_ages / sequential_wor_*)"
    )
    assert "observation_loglik_mc" not in names, (
        "observation_loglik_mc must not be the production weight default (ADR 0105)"
    )


def test_production_step_calls_wor_likelihood_not_mc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    wor_calls: list[int] = []
    mc_calls: list[int] = []
    real_wor = age_likelihood.log_p_sales_waste_given_ages
    real_mc = backends.observation_loglik_mc

    def _spy_wor(*args: Any, **kwargs: Any) -> Any:
        wor_calls.append(1)
        return real_wor(*args, **kwargs)

    def _spy_mc(*args: Any, **kwargs: Any) -> Any:
        mc_calls.append(1)
        return real_mc(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "log_p_sales_waste_given_ages", _spy_wor)
    if hasattr(backends, "log_p_sales_waste_given_ages"):
        monkeypatch.setattr(backends, "log_p_sales_waste_given_ages", _spy_wor)
    monkeypatch.setattr(backends, "observation_loglik_mc", _spy_mc)

    rbpf = RBPF(params=ModelParams(), N=20, K=4, L=2)
    rng = np.random.default_rng(3)
    rbpf.initialize(rng)
    rbpf.step(_p1_unobserved_maps(), rng)
    assert wor_calls, "default production step must score via exact WOR likelihood"
    assert not mc_calls, "default production step must not call observation_loglik_mc"


# ---------------------------------------------------------------------------
# AC: sales_likelihood config — default exact WOR; multinomial selectable
# ---------------------------------------------------------------------------


def test_rbpf_sales_likelihood_field_defaults_to_exact_sequential_wor() -> None:
    field_names = {f.name for f in dataclasses.fields(RBPF)}
    assert "sales_likelihood" in field_names, (
        "RBPF must expose sales_likelihood config (ADR 0105)"
    )
    field = next(f for f in dataclasses.fields(RBPF) if f.name == "sales_likelihood")
    assert field.default == "exact_sequential_wor"
    rbpf = RBPF(params=ModelParams(), N=8, K=4, L=2)
    assert rbpf.sales_likelihood == "exact_sequential_wor"


def test_rbpf_sales_likelihood_multinomial_selectable() -> None:
    field_names = {f.name for f in dataclasses.fields(RBPF)}
    assert "sales_likelihood" in field_names
    rbpf = RBPF(
        params=ModelParams(),
        N=8,
        K=4,
        L=2,
        sales_likelihood="multinomial",
    )
    assert rbpf.sales_likelihood == "multinomial"


# ---------------------------------------------------------------------------
# AC: count transitions match day_step physics — not ±1 RW
# ---------------------------------------------------------------------------


def test_rbpf_update_has_no_pm1_count_random_walk() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    assert not _has_pm1_count_rw(fn), (
        "production _rbpf_update must not use rng.integers(-1, 2, ...) count RW; "
        "count transitions must match day_step / allocate_sales physics (ADR 0105)"
    )


def test_rbpf_update_count_path_names_day_step_physics() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn) | _attr_names_in_function(fn)
    physics = names & {"day_step", "allocate_sales", "death_prob_survival_ratio"}
    assert physics, (
        "production count update must reference day_step-consistent kernels "
        "(day_step / allocate_sales / death_prob_survival_ratio)"
    )


# ---------------------------------------------------------------------------
# AC: arrival-only ages — no in-store age rewrite under P1 sales
# ---------------------------------------------------------------------------


def test_p1_step_keeps_age_post_equal_to_clocked_prior_when_no_births() -> None:
    """With arrivals=0, sales must not rewrite age_post rows (arrival-only)."""
    rbpf = RBPF(params=ModelParams(), N=30, K=6, L=2)
    rng = np.random.default_rng(23)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
    prior = np.ones_like(rbpf._state.age_post) / rbpf._state.age_post.shape[-1]
    rbpf._state.age_post[:] = prior
    age_before = rbpf._state.age_post.copy()

    obs = _p1_unobserved_maps(sales_total=12, waste_total=1, arrivals=0)
    rbpf.step(obs, rng)
    assert rbpf._state is not None
    age_after = rbpf._state.age_post
    row_sums = age_after.sum(axis=-1)
    assert np.allclose(row_sums, 1.0, atol=_SIMPLEX_TOL)
    tv = _lot_tv(age_before.reshape(-1), age_after.reshape(-1))
    assert tv <= _TV_TOL, (
        f"age_post TV={tv:.3g} after P1 sales — in-store LL must not rewrite ages "
        "(ADR 0105 arrival-only; clock/birth only)"
    )


def test_mean_field_update_remains_importable_for_diagnostics() -> None:
    from blueberries_voi.filter.age_likelihood import (
        exact_joint_update,
        mean_field_update,
    )

    assert callable(mean_field_update)
    assert callable(exact_joint_update)
