"""T-068 / ADR 0105 production filter contracts (supersedes ADR 0091 age-MF settle).

Former T-021 guards required production ``mean_field_update`` / MC weights /
``PRODUCTION_BACKEND == "mean_field"``. Those bans are replaced here.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi import filter as filter_pkg
from blueberries_voi.filter import RBPF
from blueberries_voi.filter.backends import BACKENDS, get_backend
from blueberries_voi.filter.types import (
    MAX_JOINT_FLOATS,
    UNOBSERVED,
    P1Obs,
    RichObs,
    joint_state_count,
    mask_for,
)
from blueberries_voi.model import ModelParams

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROD_K = 8
_PROD_N = 2000
_L_OVER = 5  # 8^5 * 2000 > MAX_JOINT_FLOATS
_L_LONG = 8
_TV_TOL = 1e-9
_SIMPLEX_TOL = 1e-6

# Runtime deps locked — ticket must not add packages.
_RUNTIME_DEPS_LOCKED = frozenset({"numpy", "scipy"})  # ADR 0101 / T-046 slim core


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


def _p1_unobserved_maps(
    *,
    sales_total: int = 10,
    waste_total: int = 2,
    arrivals: int = 0,
) -> RichObs:
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


def _f1_lot_maps(
    *,
    sales_by_lot: dict[int, int],
    sales_total: int | None = None,
) -> RichObs:
    total = sales_total if sales_total is not None else int(sum(sales_by_lot.values()))
    return mask_for("F1").apply(
        RichObs(
            arrivals=0,
            sales_total=total,
            waste_total=0,
            sales_by_lot=sales_by_lot,
            waste_by_lot=UNOBSERVED,
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=frozenset(sales_by_lot),
        )
    )


def _lot_tv(a: np.ndarray, b: np.ndarray) -> float:
    return 0.5 * float(
        np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).sum()
    )


def _has_pm1_count_rw(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_integers = (isinstance(func, ast.Attribute) and func.attr == "integers") or (
            isinstance(func, ast.Name) and func.id == "integers"
        )
        if not is_integers or len(node.args) < 2:
            continue
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
# AC: PRODUCTION_BACKEND is not age mean-field (ADR 0105)
# ---------------------------------------------------------------------------


def test_production_backend_constant_is_not_mean_field() -> None:
    assert filter_pkg.PRODUCTION_BACKEND != "mean_field", (
        "ADR 0105: PRODUCTION_BACKEND must not remain the age mean-field settle"
    )
    assert filter_pkg.PRODUCTION_BACKEND not in {
        "sliding_window",
        "full_joint",
    }


def test_default_rbpf_matches_production_backend_not_age_mf() -> None:
    assert filter_pkg.PRODUCTION_BACKEND != "mean_field"
    rbpf = RBPF(params=ModelParams(), N=40, K=4, L=2)
    choice = getattr(rbpf, "backend_choice", None)
    assert choice is not None, "RBPF must expose backend_choice"
    backend_name = getattr(choice, "backend", None)
    assert backend_name == filter_pkg.PRODUCTION_BACKEND
    assert backend_name not in {"sliding_window", "full_joint", "mean_field"}


# ---------------------------------------------------------------------------
# AC: no mean_field_update on production path; arrival-only ages
# ---------------------------------------------------------------------------


def test_rbpf_update_source_does_not_call_mean_field_update() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    assert "mean_field_update" not in names


def test_p1_unobserved_maps_does_not_invoke_mean_field_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    calls: list[tuple[Any, ...]] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
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
    rbpf.step(obs, rng)
    assert not calls, "mean_field_update must not run on production P1 path"


def test_p1_age_rows_stay_simplex_and_do_not_move_under_sales_ll() -> None:
    """Arrival-only: non-flat P1 sales must not rewrite age_post (no in-store LL)."""
    rbpf = RBPF(params=ModelParams(), N=30, K=6, L=2)
    rng = np.random.default_rng(23)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
    prior = np.ones_like(rbpf._state.age_post) / rbpf._state.age_post.shape[-1]
    rbpf._state.age_post[:] = prior
    prior_lot0 = rbpf.age_posterior(0).copy()

    obs = _p1_unobserved_maps(sales_total=12, waste_total=1, arrivals=0)
    rbpf.step(obs, rng)
    assert rbpf._state is not None
    post = rbpf._state.age_post
    assert np.allclose(post.sum(axis=-1), 1.0, atol=_SIMPLEX_TOL)
    post_lot0 = rbpf.age_posterior(0)
    tv = _lot_tv(prior_lot0, post_lot0)
    assert tv <= _TV_TOL, (
        f"lot-0 age marginal TV={tv:.3g} — sales must not rewrite arrival ages"
    )


# ---------------------------------------------------------------------------
# AC: default particle weights = exact WOR (not MC)
# ---------------------------------------------------------------------------


def test_production_weights_use_exact_wor_not_observation_loglik_mc() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    assert "observation_loglik_mc" not in names, (
        "particle weights must not default to observation_loglik_mc (ADR 0105)"
    )
    wor = names & {
        "log_p_sales_waste_given_ages",
        "sequential_wor_pmf",
        "sequential_wor_composition_prob",
        "sequential_wor_composition_probs",
    }
    assert wor, "production weights must use exact sequential WOR scorers"


def test_production_step_does_not_call_observation_loglik_mc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    real = backends.observation_loglik_mc

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(backends, "observation_loglik_mc", _spy)
    rbpf = RBPF(params=ModelParams(), N=20, K=4, L=2)
    rng = np.random.default_rng(3)
    rbpf.initialize(rng)
    rbpf.step(_p1_unobserved_maps(), rng)
    assert not calls, "default production step must not call observation_loglik_mc"


# ---------------------------------------------------------------------------
# AC: lot maps must not rewrite ages either (arrival-only)
# ---------------------------------------------------------------------------


def test_lot_map_path_does_not_invoke_apply_lot_map_age_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    if not hasattr(backends, "_apply_lot_map_age_update"):
        pytest.skip("_apply_lot_map_age_update already removed")
    real = backends._apply_lot_map_age_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(backends, "_apply_lot_map_age_update", _spy)
    rbpf = RBPF(params=ModelParams(), N=40, K=4, L=2)
    rng = np.random.default_rng(17)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
    obs = _f1_lot_maps(sales_by_lot={1: 10, 2: 2})
    rbpf.step(obs, rng)
    assert not calls, (
        "ADR 0105: production path must not apply in-store lot-map age LL updates"
    )


def test_lot_map_excess_does_not_move_target_lot_age_marginal() -> None:
    def _posts(
        sales_by_lot: dict[int, int], *, seed: int
    ) -> tuple[np.ndarray, np.ndarray]:
        rbpf = RBPF(params=ModelParams(), N=60, K=4, L=2)
        rng = np.random.default_rng(seed)
        rbpf.initialize(rng)
        assert rbpf._state is not None
        rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
        flat = np.ones_like(rbpf._state.age_post) / rbpf._state.age_post.shape[-1]
        rbpf._state.age_post[:] = flat
        rbpf.step(_f1_lot_maps(sales_by_lot=sales_by_lot), rng)
        return rbpf.age_posterior(0), rbpf.age_posterior(1)

    base_a, _base_b = _posts({1: 6, 2: 6}, seed=19)
    excess_a, _excess_b = _posts({1: 10, 2: 2}, seed=19)
    delta_a = _lot_tv(base_a, excess_a)
    assert delta_a <= _TV_TOL, (
        "lot-map sales must not rewrite age marginals under arrival-only ages"
    )


# ---------------------------------------------------------------------------
# AC: counts not ±1 RW; over-budget constructs without MemoryError
# ---------------------------------------------------------------------------


def test_rbpf_update_has_no_pm1_count_random_walk() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    assert not _has_pm1_count_rw(fn)


def test_choose_backend_not_joint_stub_when_over_budget() -> None:
    choose = filter_pkg.choose_backend
    assert joint_state_count(_PROD_K, _L_OVER, _PROD_N) > MAX_JOINT_FLOATS
    choice = choose(_PROD_K, _L_OVER, _PROD_N)
    assert choice.backend not in {"sliding_window", "full_joint"}
    assert choice.L == _L_OVER
    assert choice.K == _PROD_K
    assert choice.N == _PROD_N


def test_choose_backend_preserves_long_dwell_l_no_silent_truncation() -> None:
    choice = filter_pkg.choose_backend(_PROD_K, _L_LONG, _PROD_N)
    assert choice.L == _L_LONG
    assert choice.backend not in {"sliding_window", "full_joint"}


def test_production_rbpf_over_budget_constructs_without_memory_error() -> None:
    assert joint_state_count(_PROD_K, _L_LONG, _PROD_N) > MAX_JOINT_FLOATS
    try:
        rbpf = RBPF(
            params=ModelParams(),
            K=_PROD_K,
            N=_PROD_N,
            L=_L_LONG,
        )
    except MemoryError as exc:
        raise AssertionError(
            "production path must not raise MemoryError on over-budget (K,L,N)"
        ) from exc
    assert rbpf.L == _L_LONG
    assert rbpf.backend_choice.backend not in {"sliding_window", "full_joint"}


# ---------------------------------------------------------------------------
# AC: bakeoff A-E retained; MF/MC remain importable off production path
# ---------------------------------------------------------------------------


def test_bakeoff_registry_still_exposes_arms_a_through_e() -> None:
    assert set(BACKENDS) == {
        "sliding_window",
        "mean_field",
        "bound_L",
        "bootstrap_pf",
        "full_joint",
    }
    for name in BACKENDS:
        be = get_backend(name)
        assert getattr(be, "name", None) == name


def test_full_joint_bakeoff_arm_still_guards_memory_production_does_not() -> None:
    k, ell, n = _PROD_K, _L_LONG, _PROD_N
    assert joint_state_count(k, ell, n) > MAX_JOINT_FLOATS
    choice = filter_pkg.choose_backend(k, ell, n)
    assert choice.backend not in {"sliding_window", "full_joint"}
    rbpf = RBPF(params=ModelParams(), K=k, N=n, L=ell)
    assert rbpf.backend_choice.backend not in {"sliding_window", "full_joint"}

    be = get_backend("full_joint")
    rng = np.random.default_rng(0)
    with pytest.raises(MemoryError, match="budget exceeded"):
        be.initialize(N=n, K=k, L=ell, params=ModelParams(), rng=rng)


def test_mean_field_update_and_mc_ll_remain_importable() -> None:
    from blueberries_voi.filter.age_likelihood import mean_field_update
    from blueberries_voi.filter.backends import observation_loglik_mc

    assert callable(mean_field_update)
    assert callable(observation_loglik_mc)


# ---------------------------------------------------------------------------
# AC: ADR 0105 accepted; ADR 0091 superseded for production; no new deps
# ---------------------------------------------------------------------------


def test_adr_0105_accepted_and_supersedes_production_mf() -> None:
    adr = _REPO_ROOT / ".team" / "adr"
    text_0105 = (adr / "0105-arrival-only-age-counts-only-exact-wor.md").read_text(
        encoding="utf-8"
    )
    status = [ln.strip() for ln in text_0105.splitlines() if ln.startswith("STATUS:")]
    assert status and status[0] == "STATUS: ACCEPTED"
    assert "mean_field_update" in text_0105
    assert (
        "exact sequential" in text_0105.lower() or "exact_sequential_wor" in text_0105
    )

    text_0091 = (adr / "0091-fil13-production-mean-field.md").read_text(
        encoding="utf-8"
    )
    # Historical ADR may remain ACCEPTED; production role is superseded by 0105.
    assert "STATUS:" in text_0091


def test_no_new_runtime_dependencies_for_t068() -> None:
    import tomllib

    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _RUNTIME_DEPS_LOCKED, (
        f"runtime dependencies changed for T-068: {sorted(names)} "
        f"(locked {sorted(_RUNTIME_DEPS_LOCKED)})"
    )


def test_legacy_p1obs_step_still_accepted_on_production_path() -> None:
    rbpf = RBPF(params=ModelParams(), N=16, K=4, L=2)
    rng = np.random.default_rng(5)
    rbpf.initialize(rng)
    summary = rbpf.step(P1Obs(10, 1, 0), rng)
    assert summary.ess > 0
