"""T-032 ENG-04 M2 gates - expected RED until M2 gate wiring lands.

CI gate names locked by ``.team/specs/T-032.md`` Interfaces:

* ``test_beta1_degeneracy`` - age-aware == age-blind when ``w`` is constant
* ``test_crn_desync_gate`` - T-030 ``detect_crn_desync`` wired into M2 gates
* ``test_dp_certificate_gate`` - T-031 DP-gap report/assertion wired

Gates are library helpers under ``sim`` (mirroring package layout); the pytest
node ids above are the CI contract.
"""

from __future__ import annotations

import importlib
import inspect
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

_GATE_MODULE_CANDIDATES: tuple[str, ...] = (
    "blueberries_voi.sim.m2_gates",
    "blueberries_voi.sim.m2_ladder",
)

_BETA1_ATTRS: tuple[str, ...] = (
    "assert_beta1_degeneracy",
    "run_beta1_degeneracy_gate",
    "beta1_degeneracy_gate",
)
_CRN_ATTRS: tuple[str, ...] = (
    "assert_crn_desync",
    "run_crn_desync_gate",
    "crn_desync_gate",
)
_DP_ATTRS: tuple[str, ...] = (
    "assert_dp_certificate",
    "run_dp_certificate_gate",
    "dp_certificate_gate",
    "report_dp_gap",
)


def _resolve_gate_module() -> Any:
    errors: list[str] = []
    for name in _GATE_MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
    pytest.fail(
        "T-032 ENG-04 gates require m2_gates / m2_ladder module "
        f"(tried {list(_GATE_MODULE_CANDIDATES)}): {'; '.join(errors)}",
        pytrace=False,
    )


def _resolve_gate(attr_candidates: tuple[str, ...]) -> Any:
    mod = _resolve_gate_module()
    for attr in attr_candidates:
        found = getattr(mod, attr, None)
        if found is not None:
            return found
    pytest.fail(
        "missing ENG-04 gate export; expected one of "
        f"{list(attr_candidates)} on {mod.__name__}",
        pytrace=False,
    )


def _call_gate(gate: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(gate)
    if not sig.parameters:
        return gate()
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    if filtered:
        return gate(**filtered)
    return gate()


def _gate_ok(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    ok = getattr(result, "ok", None)
    if ok is None and isinstance(result, Mapping):
        ok = result.get("ok", result.get("passed"))
    if ok is None:
        status = getattr(result, "status", None)
        if status is None and isinstance(result, Mapping):
            status = result.get("status")
        if status is not None:
            return str(status).lower() in {"ok", "pass", "passed", "green"}
    if ok is None:
        pytest.fail(
            f"gate result must expose ok/passed/status, got {result!r}",
            pytrace=False,
        )
    return bool(ok)


def _extract_gap(result: Any) -> float | None:
    if isinstance(result, (int, float)):
        return float(result)
    gap = getattr(result, "gap", None)
    if gap is None:
        gap = getattr(result, "gap_vs_rollout", None)
    if gap is None and isinstance(result, Mapping):
        gap = result.get("gap", result.get("gap_vs_rollout"))
    if gap is None:
        report = getattr(result, "report", None)
        if report is None and isinstance(result, Mapping):
            report = result.get("report")
        if report is not None:
            return _extract_gap(report)
    return float(gap) if gap is not None else None


# ---------------------------------------------------------------------------
# AC: automated beta=1 degeneracy (age-aware == age-blind when w constant)
# ---------------------------------------------------------------------------


def test_beta1_degeneracy() -> None:
    """ENG-04 / CTL-05: constant-w age-aware and age-blind orders coincide."""
    gate = _resolve_gate(_BETA1_ATTRS)
    assert callable(gate)
    result = _call_gate(gate)
    assert _gate_ok(result), (
        f"beta=1 / constant-w degeneracy gate must pass; got {result!r}"
    )

    # Must drive the age-aware side through real SW / effective_inventory — not a
    # hand copy of the Rung 0 formula (CI red if that wiring regresses).
    mod = _resolve_gate_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "DampedSurvivalWeightedPolicy" in source, (
        "beta=1 gate must compare against DampedSurvivalWeightedPolicy"
    )
    assert "effective_inventory" in source, (
        "beta=1 gate must wire effective_inventory for the flat-w fixture"
    )
    assert "CorrectedAgeBlindPolicy" in source


def test_beta1_degeneracy_orders_match_on_same_age_fixture() -> None:
    """Direct order equality: would fail if SW and Rung 0 diverge under flat w."""
    from scipy.stats import nbinom

    from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
    from blueberries_voi.filter.belief import ShelfBelief, effective_inventory
    from blueberries_voi.model import ModelParams
    from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy

    params = ModelParams(case_size=8)
    alpha, rho = 0.9, 1.0
    grid = [0.0, 1.0, 2.0, 3.0, 4.0]
    lots = [20.0, 20.0]
    pending = {1: 16}
    margs = [[1.0, 0.0, 0.0, 0.0, 0.0] for _ in lots]
    belief = ShelfBelief(lot_counts=lots, age_marginals=margs, tau_grid=grid)

    bar_w = float(
        effective_inventory(
            ShelfBelief(lot_counts=[1.0], age_marginals=[margs[0]], tau_grid=grid),
            pending_orders={},
            params=params,
        )
    )
    pipe_w = float(
        effective_inventory(
            ShelfBelief(lot_counts=[0.0], age_marginals=[margs[0]], tau_grid=grid),
            pending_orders={1: 1},
            params=params,
        )
    )
    # Matched legacy scalar window for flat-w unit equality. MWF schedule /
    # day-indexed gate path is locked in tests/test_t083_baselines_rollout_m2.py
    # (T-083 supersedes immutable daily-2 as the scientific base case).
    d_star = float(nbinom.ppf(alpha, params.nb_r() * 2.0, params.nb_p()))

    q_blind = CorrectedAgeBlindPolicy(
        alpha=alpha,
        params=params,
        rho=rho,
        mean_survival_weight=bar_w,
        pipeline_weight=pipe_w,
        demand_target=d_star,
        protection_days=2,
        case_size=8,
    ).order(0, belief, pending_orders=pending)
    q_aware = DampedSurvivalWeightedPolicy(rho=rho, alpha=alpha, params=params).order(
        belief, pending_orders=pending
    )
    assert int(q_blind) == int(q_aware)


def test_beta1_degeneracy_gate_documents_constant_w_contract() -> None:
    gate = _resolve_gate(_BETA1_ATTRS)
    mod = _resolve_gate_module()
    doc = f"{mod.__doc__ or ''}\n{getattr(gate, '__doc__', None) or ''}".lower()
    assert "beta" in doc or "degeneracy" in doc
    assert (
        "constant" in doc
        or "flat" in doc
        or "age-blind" in doc
        or "age_blind" in doc
        or "rung" in doc
    )


# ---------------------------------------------------------------------------
# AC: CRN desync detector from T-030 wired into M2 gate set
# ---------------------------------------------------------------------------


def test_crn_desync_gate() -> None:
    """ENG-04: M2 gate wraps T-030 detect_crn_desync (CI red if broken)."""
    gate = _resolve_gate(_CRN_ATTRS)
    assert callable(gate)
    result = _call_gate(gate, crossed=False, desync=False, force_desync=False)
    assert _gate_ok(result), (
        f"CRN desync gate must pass on correct streams; got {result!r}"
    )

    mod = _resolve_gate_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "detect_crn_desync" in source, (
        "crn desync gate must wire "
        "blueberries_voi.sim.bakeoff_rollout.detect_crn_desync"
    )


def test_crn_desync_gate_fails_when_streams_crossed() -> None:
    """CI red path: intentional desync must not report ok."""
    gate = _resolve_gate(_CRN_ATTRS)
    mod = _resolve_gate_module()

    fail_fn = getattr(mod, "assert_crn_desync_fails_when_crossed", None)
    if callable(fail_fn):
        fail_fn()
        return

    probe = getattr(mod, "probe_crn_desync_crossed", None)
    if callable(probe):
        result = probe()
        assert not _gate_ok(result), f"crossed CRN probe must fail, got {result!r}"
        return

    sig = inspect.signature(gate)
    kwargs: dict[str, Any] = {}
    if "crossed" in sig.parameters:
        kwargs["crossed"] = True
    elif "force_desync" in sig.parameters:
        kwargs["force_desync"] = True
    elif "desync" in sig.parameters:
        kwargs["desync"] = True
    else:
        pytest.fail(
            "CRN gate must accept crossed=/force_desync=/desync= or export "
            "probe_crn_desync_crossed / assert_crn_desync_fails_when_crossed",
            pytrace=False,
        )

    result = gate(**kwargs)
    assert not _gate_ok(result), f"crossed CRN must fail the M2 gate, got {result!r}"


# ---------------------------------------------------------------------------
# AC: DP certificate / gap report from T-031 wired
# ---------------------------------------------------------------------------


def test_dp_certificate_gate() -> None:
    """ENG-04: M2 gate requires T-031 DP-gap report (CI red if broken/missing)."""
    gate = _resolve_gate(_DP_ATTRS)
    assert callable(gate)
    result = _call_gate(gate)

    gap = _extract_gap(result)
    assert gap is not None, (
        "DP certificate gate must report a numeric gap_vs_rollout (T-031)"
    )
    assert math.isfinite(gap)
    assert gap >= 0.0
    if hasattr(result, "ok") or (
        isinstance(result, Mapping) and ("ok" in result or "passed" in result)
    ):
        assert _gate_ok(result)


def test_dp_certificate_gate_wires_gap_vs_rollout() -> None:
    mod = _resolve_gate_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "gap_vs_rollout" in source or "solve_toy_dp" in source, (
        "DP certificate gate must wire T-031 gap_vs_rollout / solve_toy_dp"
    )
