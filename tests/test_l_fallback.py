"""T-015 Dynamic L + joint→sliding_window fallback (RED / acceptance)."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi import filter as filter_pkg
from blueberries_voi.filter import RBPF
from blueberries_voi.filter.types import MAX_JOINT_FLOATS, joint_state_count
from blueberries_voi.model import ModelParams

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPERIMENTS = _REPO_ROOT / "experiments"

# Production numerics (ADR 0083 / FIL-15): K=8, N=2000 → joint fits L≤4, trips at L≥5.
# (Bakeoff tables often used N=200 where the trip is near L≈6; do not copy that N here.)
_PROD_K = 8
_PROD_N = 2000
_L_WITHIN = 4  # 8^4 * 2000 = 8.192e6 ≤ 5e7
_L_OVER = 5  # 8^5 * 2000 = 6.5536e7 > 5e7
_L_LONG_DWELL = 8  # Stage A long-dwell cells ~7-8; must not truncate


def _load_attr(*module_names: str, attr: str) -> Any | None:
    for name in module_names:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        found = getattr(mod, attr, None)
        if found is not None:
            return found
    return None


def _resolve_choose_backend() -> Any:
    fn = _load_attr(
        "blueberries_voi.filter",
        "blueberries_voi.filter.rbpf",
        "blueberries_voi.filter.types",
        "blueberries_voi.filter.l_fallback",
        attr="choose_backend",
    )
    assert fn is not None, "choose_backend(K, L, N) must be exported (ADR 0089 / T-015)"
    return fn


def _resolve_backend_choice_type() -> Any:
    cls = _load_attr(
        "blueberries_voi.filter",
        "blueberries_voi.filter.rbpf",
        "blueberries_voi.filter.types",
        "blueberries_voi.filter.l_fallback",
        attr="BackendChoice",
    )
    assert cls is not None, "BackendChoice dataclass must be exported (T-015)"
    return cls


def _choice_field(choice: Any, name: str) -> Any:
    if hasattr(choice, name):
        return getattr(choice, name)
    if isinstance(choice, dict) and name in choice:
        return choice[name]
    msg = f"BackendChoice missing field {name!r}: {choice!r}"
    raise AssertionError(msg)


def _rbpf_backend_choice(rbpf: RBPF) -> Any:
    """Last BackendChoice from RBPF construct / initialize surface."""
    for attr in ("backend_choice", "last_backend_choice"):
        if hasattr(rbpf, attr):
            value = getattr(rbpf, attr)
            if value is not None:
                return value
    msg = (
        "RBPF must expose BackendChoice via backend_choice / "
        "last_backend_choice after construct or initialize"
    )
    raise AssertionError(msg)


def test_joint_budget_boundary_l4_fits_l5_trips() -> None:
    """Lock the FIL-13 float budget numbers tests rely on (prod K=8, N=2000)."""
    within = joint_state_count(_PROD_K, _L_WITHIN, _PROD_N)
    over = joint_state_count(_PROD_K, _L_OVER, _PROD_N)
    assert within <= MAX_JOINT_FLOATS
    assert over > MAX_JOINT_FLOATS


def test_choose_backend_selects_full_joint_when_within_budget() -> None:
    choose = _resolve_choose_backend()
    choice = choose(_PROD_K, _L_WITHIN, _PROD_N)
    assert _choice_field(choice, "backend") == "full_joint"
    assert _choice_field(choice, "L") == _L_WITHIN
    assert _choice_field(choice, "K") == _PROD_K
    assert _choice_field(choice, "N") == _PROD_N
    assert _choice_field(choice, "joint_floats") == pytest.approx(
        joint_state_count(_PROD_K, _L_WITHIN, _PROD_N)
    )


def test_choose_backend_selects_full_joint_at_exact_budget_edge() -> None:
    """≤ MAX_JOINT_FLOATS keeps full_joint (boundary inclusive)."""
    choose = _resolve_choose_backend()
    # Solve for N such that K^L*N == MAX_JOINT_FLOATS exactly (integer N).
    k, ell = 4, 3
    n_exact = int(MAX_JOINT_FLOATS // (k**ell))
    assert joint_state_count(k, ell, n_exact) <= MAX_JOINT_FLOATS
    choice = choose(k, ell, n_exact)
    assert _choice_field(choice, "backend") == "full_joint"


def test_choose_backend_falls_back_to_sliding_window_when_over_budget() -> None:
    choose = _resolve_choose_backend()
    choice = choose(_PROD_K, _L_OVER, _PROD_N)
    assert _choice_field(choice, "backend") == "sliding_window"
    assert _choice_field(choice, "L") == _L_OVER


def test_fallback_choice_records_structured_reason_fields() -> None:
    choose = _resolve_choose_backend()
    choice = choose(_PROD_K, _L_LONG_DWELL, _PROD_N)
    assert _choice_field(choice, "backend") == "sliding_window"
    assert _choice_field(choice, "K") == _PROD_K
    assert _choice_field(choice, "L") == _L_LONG_DWELL
    assert _choice_field(choice, "N") == _PROD_N
    floats = _choice_field(choice, "joint_floats")
    assert floats == pytest.approx(joint_state_count(_PROD_K, _L_LONG_DWELL, _PROD_N))
    assert floats > MAX_JOINT_FLOATS
    reason = _choice_field(choice, "reason")
    assert isinstance(reason, str) and reason.strip()
    # Reason should be inspectable (K/L/N / budget / sliding_window).
    blob = reason.lower()
    assert "sliding_window" in blob or "fallback" in blob or "budget" in blob


def test_choose_backend_never_silently_truncates_l() -> None:
    """FIL-13 guard: requested L is preserved; never full_joint with smaller L."""
    choose = _resolve_choose_backend()
    requested_l = _L_LONG_DWELL
    choice = choose(_PROD_K, requested_l, _PROD_N)
    assert _choice_field(choice, "L") == requested_l
    assert _choice_field(choice, "backend") == "sliding_window"
    # Forbidden pattern: fit budget by shrinking L while claiming joint.
    assert not (
        _choice_field(choice, "backend") == "full_joint"
        and _choice_field(choice, "L") < requested_l
    )


def test_rbpf_within_budget_uses_full_joint() -> None:
    try:
        rbpf = RBPF(
            params=ModelParams(),
            K=_PROD_K,
            N=200,
            L=3,
        )
    except MemoryError as exc:
        raise AssertionError(
            "within-budget RBPF must construct without MemoryError"
        ) from exc
    choice = _rbpf_backend_choice(rbpf)
    assert _choice_field(choice, "backend") == "full_joint"
    assert rbpf.L == 3


def test_rbpf_over_budget_falls_back_without_memory_error() -> None:
    try:
        rbpf = RBPF(
            params=ModelParams(),
            K=_PROD_K,
            N=_PROD_N,
            L=_L_LONG_DWELL,
        )
    except MemoryError as exc:
        raise AssertionError(
            "over-budget L must auto-fallback to sliding_window, "
            "not raise MemoryError (ADR 0089)"
        ) from exc
    choice = _rbpf_backend_choice(rbpf)
    assert _choice_field(choice, "backend") == "sliding_window"
    assert rbpf.L == _L_LONG_DWELL
    backend = getattr(rbpf, "_backend", None)
    assert getattr(backend, "name", None) == "sliding_window"


def test_rbpf_initialize_over_budget_preserves_l_and_falls_back() -> None:
    """initialize(L=…) must not truncate L to fit joint; fallback instead."""
    # Start within budget at production N, then raise L past the joint ceiling.
    rbpf = RBPF(params=ModelParams(), K=_PROD_K, N=_PROD_N, L=3)
    assert joint_state_count(_PROD_K, 3, _PROD_N) <= MAX_JOINT_FLOATS
    assert joint_state_count(_PROD_K, _L_OVER, _PROD_N) > MAX_JOINT_FLOATS
    try:
        rbpf.initialize(np.random.default_rng(0), L=_L_OVER)
    except MemoryError as exc:
        raise AssertionError(
            "initialize with over-budget L must fallback, not MemoryError"
        ) from exc
    assert rbpf.L == _L_OVER
    choice = _rbpf_backend_choice(rbpf)
    assert _choice_field(choice, "backend") == "sliding_window"
    assert _choice_field(choice, "L") == _L_OVER


def test_dynamic_l_follows_configured_max_when_joint_fits() -> None:
    """No permanent hard-code ignoring measured/configured L when safe."""
    configured_l = 4
    assert joint_state_count(_PROD_K, configured_l, 200) <= MAX_JOINT_FLOATS
    try:
        rbpf = RBPF(
            params=ModelParams(),
            K=_PROD_K,
            N=200,
            L=configured_l,
        )
    except MemoryError as exc:
        raise AssertionError("configured L within budget must not MemoryError") from exc
    assert configured_l == rbpf.L
    choice = _rbpf_backend_choice(rbpf)
    assert _choice_field(choice, "backend") == "full_joint"
    assert _choice_field(choice, "L") == configured_l
    # Dynamic path must not clamp to legacy PRODUCTION_L=3 when 4 is safe.
    assert rbpf.L != 3 or configured_l == 3


def test_production_default_remains_full_joint_fil12_not_reopened() -> None:
    """FIL-12=B stays the production preference; sliding_window is FIL-13 fallback."""
    assert filter_pkg.PRODUCTION_BACKEND == "full_joint"
    choose = _resolve_choose_backend()
    within = choose(_PROD_K, 3, _PROD_N)
    assert _choice_field(within, "backend") == "full_joint"
    over = choose(_PROD_K, _L_OVER, _PROD_N)
    assert _choice_field(over, "backend") == "sliding_window"
    # Fallback arm must not quietly reopen mean-field / bound_L as production.
    assert _choice_field(over, "backend") not in {
        "mean_field",
        "bound_L",
        "bootstrap_pf",
    }


def test_backend_choice_type_is_frozen_structured_record() -> None:
    cls = _resolve_backend_choice_type()
    choose = _resolve_choose_backend()
    choice = choose(_PROD_K, _L_OVER, _PROD_N)
    assert isinstance(choice, cls)
    # Frozen / immutable record (dataclass frozen=True in the spec).
    with pytest.raises((AttributeError, TypeError)):
        choice.backend = "mean_field"


def test_m25_l_remeasure_experiment_note_documents_fallback() -> None:
    """AC: dedicated M2.5 addendum (not the M1 fil13 bakeoff alone)."""
    # Prefer an explicit new note; do not treat M1 fil13_*.md as sufficient.
    preferred = _EXPERIMENTS / "m25_l_remeasure.md"
    candidates = [preferred] if preferred.is_file() else []
    if not candidates:
        candidates = sorted(
            p
            for p in (
                *_EXPERIMENTS.glob("*m25*"),
                *_EXPERIMENTS.glob("*dynamic*l*"),
                *_EXPERIMENTS.glob("*l_remeasure*"),
                *_EXPERIMENTS.glob("*l_fallback*"),
            )
            if p.is_file() and p.suffix in {".md", ".txt"}
        )
    assert candidates, (
        "expected experiments/m25_l_remeasure.md (or *m25* / *l_remeasure* "
        "addendum) documenting M2.5 open-loop + long-dwell L and fallback"
    )

    combined = "\n".join(p.read_text(encoding="utf-8") for p in candidates)
    lower = combined.lower()
    has_m25 = "m2.5" in lower or "m25" in lower
    has_open_loop = "open-loop" in lower or "open loop" in lower
    has_long_dwell = "long-dwell" in lower or "long dwell" in lower
    has_remeasure = bool(re.search(r"re-?measur|empirical\s+l|live\s+cohort", lower))
    has_fallback = "sliding_window" in lower and (
        "fallback" in lower or "budget" in lower
    )
    covered = (
        has_m25 and has_open_loop and has_long_dwell and has_remeasure and has_fallback
    )
    assert covered, (
        "M2.5 note must cover open-loop + long-dwell L remeasure and "
        "sliding_window fallback; files: "
        + ", ".join(str(p.relative_to(_REPO_ROOT)) for p in candidates)
    )
