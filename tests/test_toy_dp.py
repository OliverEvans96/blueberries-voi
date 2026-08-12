"""T-031 CTL-06 toy exact DP certificate — RED acceptance contracts.

Locks ADR 0063 (CTL-06=A), ADR 0059 (gap adjudicates single-step rollout),
and `.team/specs/T-031.md` before production ``controller/toy_dp.py`` exists.

Frozen toy instance (CI runtime target: under a few seconds):

* demand support ``{0, 1, 2}``
* τ grid length ≤ 4 (truncated ages)
* ``max_lots = 2``; small max inventory
* short horizon (≤ 4 decision epochs)

β=1 / constant-``w`` trap (ADR 0063): age-aware
``DampedSurvivalWeightedPolicy.delta_tau_L`` must equal the Rung 0 / toy
protection convention on the same instance (daily LT=1 → R+L=2 /
``protection_days=2``).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.model import ModelParams, q10_age_increment

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROLLER_DIR = _REPO_ROOT / "src" / "blueberries_voi" / "controller"
_CONTROLLER_PKG = "blueberries_voi.controller"
_TOY_MODULE = "blueberries_voi.controller.toy_dp"
_TOY_MODULE_CANDIDATES = (
    _TOY_MODULE,
    "blueberries_voi.controller.dp",
    "blueberries_voi.controller.exact_dp",
    "blueberries_voi.controller",
)

# ---------------------------------------------------------------------------
# Fixture locks (open question in T-031: keep CI under a few seconds)
# ---------------------------------------------------------------------------
_DEMAND_SUPPORT: tuple[int, ...] = (0, 1, 2)
_TAU_BINS: tuple[float, ...] = (0.0, 1.0, 2.0, 3.0)  # length ≤ 4
_MAX_LOTS: int = 2
_MAX_INVENTORY: int = 4
_HORIZON: int = 3  # short decision horizon
_LEAD_TIME_DAYS: int = 1
_PROTECTION_DEMAND_DAYS: int = 2  # R+L under daily LT=1 (X-11 / ADR 0006)
_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyarrow", "pyarrow.parquet"})

_VALUE_TABLE_ATTRS = ("value_table", "values", "V", "optimal_values")
_POLICY_TABLE_ATTRS = ("policy_table", "policy", "pi", "optimal_policy")


def _resolve_toy_module() -> Any:
    """Locate ``controller.toy_dp`` (or agreed CTL-06 module)."""
    last_err: Exception | None = None
    for name in _TOY_MODULE_CANDIDATES:
        try:
            mod = importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
        if name == _CONTROLLER_PKG:
            if getattr(mod, "solve_toy_dp", None) is not None:
                return mod
            continue
        return mod
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        f"controller.toy_dp (or agreed module) must exist for T-031 / ADR 0063; "
        f"tried {_TOY_MODULE_CANDIDATES}{detail}",
        pytrace=False,
    )


def _resolve_attr(name: str) -> Any:
    mod = _resolve_toy_module()
    found = getattr(mod, name, None)
    if found is not None:
        return found
    pkg = importlib.import_module(_CONTROLLER_PKG)
    found = getattr(pkg, name, None)
    if found is not None:
        return found
    pytest.fail(
        f"{name} must be exported from {_TOY_MODULE} (or controller package) "
        f"per .team/specs/T-031.md",
        pytrace=False,
    )


def _toy_kwargs() -> dict[str, Any]:
    """Keyword args matching the locked toy grid when the API accepts them."""
    return {
        "demand_support": _DEMAND_SUPPORT,
        "tau_bins": _TAU_BINS,
        "max_lots": _MAX_LOTS,
        "max_inventory": _MAX_INVENTORY,
        "horizon": _HORIZON,
        "lead_time_days": _LEAD_TIME_DAYS,
        "protection_demand_days": _PROTECTION_DEMAND_DAYS,
    }


def _filter_kwargs(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    has_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if has_var_kw:
        named = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return named if named else dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def _call_solve_toy_dp(solve: Any) -> Any:
    """Invoke ``solve_toy_dp`` with locked fixtures when parameters exist."""
    accepted = _filter_kwargs(solve, _toy_kwargs())
    return solve(**accepted) if accepted else solve()


def _table_attr(result: Any, candidates: tuple[str, ...], *, kind: str) -> Any:
    for name in candidates:
        if hasattr(result, name):
            return getattr(result, name)
    pytest.fail(
        f"ToyDpResult must expose a {kind} table via one of {candidates}",
        pytrace=False,
    )


def _expected_delta_tau_l(params: ModelParams) -> float:
    """Lead-time age increment under daily LT=1 (same scalar SW exposes)."""
    return float(
        q10_age_increment(
            float(_LEAD_TIME_DAYS),
            t_store_c=params.t_store_c,
            t_ref_c=params.t_ref_c,
            q10=params.q10,
        )
    )


def _rung0_delta_tau_l(policy: Any, params: ModelParams) -> float:
    """Rung 0 / toy protection convention as a comparable scalar to SW.delta_tau_L."""
    for attr in ("delta_tau_L", "DELTA_TAU_L", "delta_tau_l"):
        got = getattr(policy, attr, None)
        if got is not None:
            return float(got)
    cls = type(policy)
    for attr in ("DELTA_TAU_L", "delta_tau_L", "delta_tau_l"):
        got = getattr(cls, attr, None)
        if got is not None:
            return float(got)
    toy = _resolve_toy_module()
    for attr in ("DELTA_TAU_L", "delta_tau_L", "TOY_DELTA_TAU_L"):
        got = getattr(toy, attr, None)
        if got is not None:
            return float(got)
    # Last resort: protection_days == R+L calendar days with LT=1 age step.
    days = getattr(policy, "protection_days", None)
    if days is None:
        days = getattr(cls, "PROTECTION_DAYS", None)
    if days == _PROTECTION_DEMAND_DAYS:
        return _expected_delta_tau_l(params)
    pytest.fail(
        "Rung 0 / toy must expose delta_tau_L (or protection_days=2 under LT=1) "
        "matching DampedSurvivalWeightedPolicy.delta_tau_L (CTL-06 trap / ADR 0063)",
        pytrace=False,
    )


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", maxsplit=1)[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
            imported.add(node.module)
    return imported


def _assert_no_file_writes(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                pytest.fail(f"{path.name} must not call open()", pytrace=False)
            if isinstance(func, ast.Attribute) and func.attr in {
                "write_text",
                "write_bytes",
                "mkdir",
                "touch",
                "dump",
                "savefig",
            }:
                pytest.fail(
                    f"{path.name} must not write files ({func.attr})",
                    pytrace=False,
                )


# ---------------------------------------------------------------------------
# AC1: solve_toy_dp backward induction → optimal value / policy table
# ---------------------------------------------------------------------------


def test_solve_toy_dp_is_exportable() -> None:
    solve = _resolve_attr("solve_toy_dp")
    assert callable(solve)


def test_toy_dp_result_type_is_exportable() -> None:
    result_type = _resolve_attr("ToyDpResult")
    assert inspect.isclass(result_type)
    assert result_type.__name__ == "ToyDpResult"


def test_solve_toy_dp_returns_optimal_value_and_policy_tables() -> None:
    """Backward induction on the locked small grid yields value + policy tables."""
    solve = _resolve_attr("solve_toy_dp")
    result_type = _resolve_attr("ToyDpResult")
    result = _call_solve_toy_dp(solve)
    assert isinstance(result, result_type)
    value_table = _table_attr(result, _VALUE_TABLE_ATTRS, kind="value")
    policy_table = _table_attr(result, _POLICY_TABLE_ATTRS, kind="policy")
    assert value_table is not None
    assert policy_table is not None
    assert len(value_table) > 0
    assert len(policy_table) > 0


def test_solve_toy_dp_uses_small_ci_state_space() -> None:
    """Toy grid stays CI-cheap: demand {0,1,2}, τ≤4, ~2 lots, short horizon."""
    solve = _resolve_attr("solve_toy_dp")
    mod = _resolve_toy_module()
    result = _call_solve_toy_dp(solve)

    demand = getattr(result, "demand_support", None)
    if demand is None:
        demand = getattr(mod, "DEMAND_SUPPORT", None)
    if demand is None:
        demand = getattr(mod, "TOY_DEMAND_SUPPORT", None)
    assert demand is not None, (
        "ToyDpResult or toy_dp module must document demand_support={0,1,2}"
    )
    assert tuple(int(x) for x in demand) == _DEMAND_SUPPORT

    lots = getattr(result, "max_lots", None)
    if lots is None:
        lots = getattr(mod, "MAX_LOTS", None)
    if lots is None:
        lots = getattr(mod, "TOY_MAX_LOTS", None)
    assert lots is not None, "toy instance must document max_lots≈2"
    assert int(lots) == _MAX_LOTS

    tau = getattr(result, "tau_bins", None)
    if tau is None:
        tau = getattr(mod, "TAU_BINS", None)
    if tau is None:
        tau = getattr(mod, "TOY_TAU_BINS", None)
    assert tau is not None, "toy instance must document truncated tau_bins"
    tau_t = tuple(tau)
    assert 2 <= len(tau_t) <= 4

    horizon = getattr(result, "horizon", None)
    if horizon is None:
        horizon = getattr(mod, "HORIZON", None)
    if horizon is None:
        horizon = getattr(mod, "TOY_HORIZON", None)
    assert horizon is not None, "toy instance must document a short horizon"
    assert 1 <= int(horizon) <= 4


# ---------------------------------------------------------------------------
# AC2: gap_vs_rollout on the same toy instance
# ---------------------------------------------------------------------------


def test_gap_vs_rollout_is_exportable() -> None:
    gap = _resolve_attr("gap_vs_rollout")
    assert callable(gap)


def test_gap_vs_rollout_reports_float_on_same_toy_instance() -> None:
    """Documented comparison: DP optimum vs rollout/base on the identical toy."""
    solve = _resolve_attr("solve_toy_dp")
    gap_fn = _resolve_attr("gap_vs_rollout")
    result = _call_solve_toy_dp(solve)
    sig = inspect.signature(gap_fn)
    names = list(sig.parameters)
    if not names:
        gap = float(gap_fn())
    elif names[0] in {"result", "toy_result", "dp_result", "optimal"} or "result" in names[
        0
    ]:
        gap = float(gap_fn(result))
    elif "solve" in names[0].lower() or names[0] in {"instance", "toy"}:
        kwargs = _filter_kwargs(gap_fn, _toy_kwargs())
        gap = float(gap_fn(**kwargs) if kwargs else gap_fn())
    else:
        gap = float(gap_fn(result))

    assert isinstance(gap, float)
    assert math.isfinite(gap)
    # Optimality gap is non-negative when defined as J* - J_rollout (or abs gap).
    assert gap >= 0.0


def test_gap_vs_rollout_documented_as_same_instance_comparison() -> None:
    mod = _resolve_toy_module()
    gap_fn = _resolve_attr("gap_vs_rollout")
    doc = f"{mod.__doc__ or ''}\n{getattr(gap_fn, '__doc__', None) or ''}".lower()
    assert "gap" in doc
    assert "rollout" in doc or "base" in doc
    assert "same" in doc or "identical" in doc or "toy" in doc


# ---------------------------------------------------------------------------
# AC3: β=1 / constant-w trap — same Δτ_L (ADR 0063)
# ---------------------------------------------------------------------------


def test_beta1_trap_age_aware_and_rung0_share_delta_tau_l_on_toy() -> None:
    """CTL-06 trap: SW.delta_tau_L equals Rung 0 / toy protection convention."""
    _resolve_toy_module()  # toy module must exist for the certificate instance
    params = ModelParams()
    sw = DampedSurvivalWeightedPolicy(rho=1.0, alpha=0.9, params=params)
    rung0 = CorrectedAgeBlindPolicy(
        alpha=0.9,
        params=params,
        rho=1.0,
        protection_days=_PROTECTION_DEMAND_DAYS,
    )

    assert sw.lead_time == _LEAD_TIME_DAYS
    assert sw.protection_demand_days == _PROTECTION_DEMAND_DAYS
    assert rung0.protection_days == _PROTECTION_DEMAND_DAYS

    sw_delta = float(sw.delta_tau_L)
    expected = _expected_delta_tau_l(params)
    assert sw_delta == pytest.approx(expected, rel=0.0, abs=1e-12)

    rung0_delta = _rung0_delta_tau_l(rung0, params)
    assert rung0_delta == pytest.approx(sw_delta, rel=0.0, abs=1e-12)

    toy = _resolve_toy_module()
    toy_delta = None
    for attr in ("DELTA_TAU_L", "delta_tau_L", "TOY_DELTA_TAU_L"):
        if getattr(toy, attr, None) is not None:
            toy_delta = float(getattr(toy, attr))
            break
    result = _call_solve_toy_dp(_resolve_attr("solve_toy_dp"))
    if toy_delta is None:
        for attr in ("delta_tau_L", "DELTA_TAU_L"):
            if hasattr(result, attr):
                toy_delta = float(getattr(result, attr))
                break
    assert toy_delta is not None, (
        "toy_dp must publish delta_tau_L for the toy instance (CTL-06 trap)"
    )
    assert toy_delta == pytest.approx(sw_delta, rel=0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# AC4: module stays pure (no matplotlib / parquet); figures outside controller/
# ---------------------------------------------------------------------------


def test_toy_dp_module_has_no_matplotlib_pyarrow_or_file_writes() -> None:
    mod = _resolve_toy_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file(), f"missing source for {mod.__name__}"
    assert "controller" in path.parts
    forbidden = _imported_roots(path) & _FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"{path.name} imports forbidden: {sorted(forbidden)}"
    _assert_no_file_writes(path)


def test_controller_package_has_no_matplotlib_or_parquet() -> None:
    """AST scan of controller/: no matplotlib / parquet; figures live elsewhere."""
    assert _CONTROLLER_DIR.is_dir()
    for path in sorted(_CONTROLLER_DIR.glob("*.py")):
        forbidden = _imported_roots(path) & _FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden: {sorted(forbidden)}"
        _assert_no_file_writes(path)


def test_toy_dp_lives_under_controller_package() -> None:
    mod = _resolve_toy_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file()
    assert path.name == "toy_dp.py" or mod.__name__.endswith(".toy_dp")
    assert "controller" in path.parts
    # Prefer the agreed module path for implementer clarity.
    preferred = _CONTROLLER_DIR / "toy_dp.py"
    assert preferred.is_file(), (
        "implementer should add src/blueberries_voi/controller/toy_dp.py"
    )


# ---------------------------------------------------------------------------
# Package surface
# ---------------------------------------------------------------------------


def test_controller_package_exports_solve_toy_dp() -> None:
    solve = _resolve_attr("solve_toy_dp")
    pkg = importlib.import_module(_CONTROLLER_PKG)
    exported = getattr(pkg, "__all__", None)
    assert isinstance(exported, list)
    assert "solve_toy_dp" in exported
    assert getattr(pkg, "solve_toy_dp", None) is solve
