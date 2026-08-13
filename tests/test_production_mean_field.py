"""T-021 Production RBPF → mean-field (FIL-13=B, FIL-04=C) — RED / acceptance."""

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

# Runtime deps locked at T-021 kickoff — ticket must not add packages.
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
    """P1 totals observed; lot maps UNOBSERVED (MF age-update path)."""
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


# ---------------------------------------------------------------------------
# AC: PRODUCTION_BACKEND / default RBPF identity is mean_field
# ---------------------------------------------------------------------------


def test_production_backend_constant_is_mean_field() -> None:
    assert filter_pkg.PRODUCTION_BACKEND == "mean_field"


def test_default_rbpf_backend_identity_is_mean_field() -> None:
    rbpf = RBPF(params=ModelParams(), N=40, K=4, L=2)
    choice = getattr(rbpf, "backend_choice", None)
    assert choice is not None, "RBPF must expose backend_choice"
    assert getattr(choice, "backend", None) == "mean_field"
    backend = getattr(rbpf, "_backend", None)
    assert getattr(backend, "name", None) == "mean_field"
    rng = np.random.default_rng(0)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    assert rbpf._state.backend == "mean_field"


# ---------------------------------------------------------------------------
# AC: P1 UNOBSERVED maps → mean_field_update; simplex; TV moves under non-flat LL
# ---------------------------------------------------------------------------


def test_rbpf_update_source_calls_mean_field_update() -> None:
    """Wiring contract: production age step names mean_field_update."""
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    assert "mean_field_update" in names, (
        "_rbpf_update must call mean_field_update on the P1 UNOBSERVED-maps path "
        "(ADR 0091 / T-021)"
    )


def test_p1_unobserved_maps_invokes_mean_field_update(
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
    assert obs.sales_by_lot is UNOBSERVED
    assert obs.waste_by_lot is UNOBSERVED
    rbpf.step(obs, rng)
    assert calls, (
        "mean_field_update was not invoked on P1 UNOBSERVED-maps production step"
    )


def test_p1_mean_field_age_rows_are_simplex_and_move_under_nonflat_ll() -> None:
    rbpf = RBPF(params=ModelParams(), N=30, K=6, L=2)
    rng = np.random.default_rng(23)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
    # Flat prior so any non-flat LL must move mass if MF is wired.
    prior = np.ones_like(rbpf._state.age_post) / rbpf._state.age_post.shape[-1]
    rbpf._state.age_post[:] = prior
    prior_lot0 = rbpf.age_posterior(0).copy()

    obs = _p1_unobserved_maps(sales_total=12, waste_total=1, arrivals=0)
    rbpf.step(obs, rng)
    assert rbpf._state is not None
    post = rbpf._state.age_post
    row_sums = post.sum(axis=-1)
    assert np.allclose(row_sums, 1.0, atol=_SIMPLEX_TOL), (
        "particle age posterior rows must form a simplex after MF update"
    )
    post_lot0 = rbpf.age_posterior(0)
    tv = _lot_tv(prior_lot0, post_lot0)
    assert tv > _TV_TOL, (
        f"lot-0 age marginal TV={tv:.3g} — posterior unchanged under non-flat P1 LL; "
        "mean_field_update not wired into production age step"
    )


# ---------------------------------------------------------------------------
# AC: particle weights still from observation_loglik_mc (not sequential_wor_pmf)
# ---------------------------------------------------------------------------


def test_production_weights_still_use_observation_loglik_mc_not_wor_pmf() -> None:
    fn = _ast_function(_backends_source(), "_rbpf_update")
    names = _names_in_function(fn)
    assert "observation_loglik_mc" in names
    assert "sequential_wor_pmf" not in names, (
        "particle weights must stay on observation_loglik_mc (ADR 0087); "
        "do not replace with sequential_wor_pmf"
    )


def test_production_step_calls_observation_loglik_mc(
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
    assert calls, "observation_loglik_mc must still score particle weights"


# ---------------------------------------------------------------------------
# AC: lot maps present → _apply_lot_map_age_update; excess lot moves
# ---------------------------------------------------------------------------


def test_lot_map_path_invokes_apply_lot_map_age_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
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
    assert obs.sales_by_lot is not UNOBSERVED
    rbpf.step(obs, rng)
    assert calls, "_apply_lot_map_age_update must run when sales_by_lot is present"


def test_lot_map_excess_moves_target_lot_age_marginal() -> None:
    def _posts(
        sales_by_lot: dict[int, int], *, seed: int
    ) -> tuple[np.ndarray, np.ndarray]:
        rbpf = RBPF(params=ModelParams(), N=60, K=4, L=2)
        rng = np.random.default_rng(seed)
        rbpf.initialize(rng)
        assert rbpf._state is not None
        rbpf._state.counts[:] = np.asarray([[8, 8]] * rbpf.N, dtype=int)
        rbpf.step(_f1_lot_maps(sales_by_lot=sales_by_lot), rng)
        return rbpf.age_posterior(0), rbpf.age_posterior(1)

    base_a, base_b = _posts({1: 6, 2: 6}, seed=19)
    excess_a, excess_b = _posts({1: 10, 2: 2}, seed=19)
    delta_a = _lot_tv(base_a, excess_a)
    delta_b = _lot_tv(base_b, excess_b)
    assert delta_a > _TV_TOL, (
        "lot with excess-above-equal-share sales did not move age marginal "
        "(lot-map age update path broken)"
    )
    assert delta_a > delta_b, (
        f"target lot Δ={delta_a:.4g} should exceed other-lot Δ={delta_b:.4g}"
    )


# ---------------------------------------------------------------------------
# AC: choose_backend always mean_field over joint budget; no silent L trunc
# ---------------------------------------------------------------------------


def test_choose_backend_returns_mean_field_when_over_joint_budget() -> None:
    choose = filter_pkg.choose_backend
    assert joint_state_count(_PROD_K, _L_OVER, _PROD_N) > MAX_JOINT_FLOATS
    choice = choose(_PROD_K, _L_OVER, _PROD_N)
    assert choice.backend == "mean_field"
    assert choice.L == _L_OVER
    assert choice.K == _PROD_K
    assert choice.N == _PROD_N


def test_choose_backend_preserves_long_dwell_l_no_silent_truncation() -> None:
    choice = filter_pkg.choose_backend(_PROD_K, _L_LONG, _PROD_N)
    assert choice.L == _L_LONG
    assert choice.backend == "mean_field"


def test_production_rbpf_over_budget_constructs_mean_field_without_memory_error() -> (
    None
):
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
            "production path must not raise MemoryError on over-budget (K,L,N); "
            "choose_backend always mean_field (ADR 0091)"
        ) from exc
    assert rbpf.backend_choice.backend == "mean_field"
    assert rbpf.L == _L_LONG
    assert getattr(rbpf._backend, "name", None) == "mean_field"


# ---------------------------------------------------------------------------
# AC: bakeoff A-E retained; full_joint guard for that arm only
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
    """Joint guard applies to bakeoff full_joint only, not production selection."""
    k, ell, n = _PROD_K, _L_LONG, _PROD_N
    assert joint_state_count(k, ell, n) > MAX_JOINT_FLOATS
    # Production selection / RBPF must not raise.
    choice = filter_pkg.choose_backend(k, ell, n)
    assert choice.backend == "mean_field"
    rbpf = RBPF(params=ModelParams(), K=k, N=n, L=ell)
    assert rbpf.backend_choice.backend == "mean_field"

    be = get_backend("full_joint")
    rng = np.random.default_rng(0)
    with pytest.raises(MemoryError, match="budget exceeded"):
        be.initialize(N=n, K=k, L=ell, params=ModelParams(), rng=rng)


# ---------------------------------------------------------------------------
# AC: ADR 0091 settle + no new runtime deps + changelog (post-green)
# ---------------------------------------------------------------------------


def test_adr_0091_accepted_and_related_cards_record_fil04_c() -> None:
    adr = _REPO_ROOT / ".team" / "adr"
    text_0091 = (adr / "0091-fil13-production-mean-field.md").read_text(
        encoding="utf-8"
    )
    status_0091 = [
        ln.strip() for ln in text_0091.splitlines() if ln.startswith("STATUS:")
    ]
    assert status_0091 and status_0091[0] == "STATUS: ACCEPTED"
    assert "2026-08-12" in text_0091

    text_0049 = (adr / "0049-fil-04-factorisation-of-age-across-cohorts.md").read_text(
        encoding="utf-8"
    )
    assert "SUPERSEDED BY 0091" in text_0049
    assert re.search(r"\bC\b.*[Mm]ean-field|[Mm]ean-field.*\bC\b", text_0049)

    text_0082 = (adr / "0082-fil-13-tractability-bakeoff.md").read_text(
        encoding="utf-8"
    )
    assert "SUPERSEDED BY 0091" in text_0082

    text_0089 = (adr / "0089-m15-dynamic-l-sliding-window-fallback.md").read_text(
        encoding="utf-8"
    )
    assert "SUPERSEDED BY 0091" in text_0089

    text_0057 = (
        adr / "0057-fil-12-making-the-joint-age-posterior-tractable.md"
    ).read_text(encoding="utf-8")
    assert "HISTORICAL" in text_0057[:240]


def test_no_new_runtime_dependencies_for_t021() -> None:
    import tomllib

    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _RUNTIME_DEPS_LOCKED, (
        f"runtime dependencies changed for T-021: {sorted(names)} "
        f"(locked {sorted(_RUNTIME_DEPS_LOCKED)})"
    )


def test_changelog_has_plain_english_production_mean_field_entry() -> None:
    """AC: after green verifier — entry describing production mean-field settle."""
    text = (_REPO_ROOT / ".team" / "changelog.md").read_text(encoding="utf-8").lower()
    has_mf = "mean-field" in text or "mean field" in text
    has_prod = "production" in text
    has_settle = (
        "fil-13" in text or "fil-04" in text or "t-021" in text or "0091" in text
    )
    assert has_mf and has_prod and has_settle, (
        ".team/changelog.md must gain a plain-English production mean-field settle "
        "entry (T-021)"
    )


def test_legacy_p1obs_step_still_accepted_on_mean_field_path() -> None:
    """Boundary: legacy P1Obs still drives the production MF path."""
    rbpf = RBPF(params=ModelParams(), N=16, K=4, L=2)
    rng = np.random.default_rng(5)
    rbpf.initialize(rng)
    summary = rbpf.step(P1Obs(10, 1, 0), rng)
    assert summary.ess > 0
