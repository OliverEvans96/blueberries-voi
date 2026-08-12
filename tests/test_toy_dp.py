"""T-031 CTL-06 toy exact DP certificate — RED acceptance contracts.

Locks ADR 0063 (CTL-06=A), ADR 0059 (gap adjudicates single-step rollout),
and `.team/specs/T-031.md` before production ``controller/toy_dp.py`` exists.

Toy grid (CI runtime target: under a few seconds):

* demand support ``{0, 1, 2}``
* truncated τ bins (few discrete ages)
* ``L_max = 2`` lots; small max inventory

β=1 / constant-``w`` trap (ADR 0063): age-aware
``DampedSurvivalWeightedPolicy.delta_tau_L`` must equal the Rung 0 / toy
protection convention on the same instance (daily LT=1 → R+L=2).
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
from blueberries_voi.model import ModelParams, q10_age_increment

_REPO_ROOT = Path(__file__).resolve().parents[1]
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
_TAU_BINS: tuple[float, ...] = (0.0, 1.0, 2.0)  # truncated τ
_MAX_LOTS: int = 2
_MAX_INVENTORY: int = 4  # small on-hand per toy instance
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
            # Package alone is not enough unless solve_toy_dp is re-exported.
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
        "lead_time_days": _LEAD_TIME_DAYS,
        "protection_demand_days": _PROTECTION_DEMAND_DAYS,
    }


def _call_solve_toy_dp(solve: Any) -> Any:
    """Invoke ``solve_toy_dp`` with locked fixtures when parameters exist."""
    sig = inspect.signature(solve)
    accepted = {k: v for k, v in _toy_kwargs().items() if k in sig.parameters}
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


def _published_delta_tau_l(obj: Any) -> float | None:
    for attr in ("delta_tau_L", "DELTA_TAU_L", "delta_tau_l", "TOY_DELTA_TAU_L"):
        got = getattr(obj, attr, None)
        if got is not None:
            return float(got)
    return None


def _call_gap_vs_rollout(gap_fn: Any, result: Any) -> float:
    """Call ``gap_vs_rollout`` with result and/or locked toy kwargs."""
    sig = inspect.signature(gap_fn)
    params = sig.parameters
    if not params:
        return float(gap_fn())
    kwargs: dict[str, Any] = {}
    for name in ("result", "toy_result", "dp_result", "optimal", "toy_dp_result"):
        if name in params:
            kwargs[name] = result
            break
    else:
        # Positional-first APIs: pass the solve result as the first argument.
        first = next(iter(params))
        if params[first].kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            for k, v in _toy_kwargs().items():
                if k in params:
                    kwargs[k] = v
            if kwargs:
                return float(gap_fn(result, **kwargs))
            return float(gap_fn(result))
    for k, v in _toy_kwargs().items():
        if k in params:
            kwargs[k] = v
    return float(gap_fn(**kwargs))


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
    # Non-empty optimal tables (exact layout is implementer's choice).
    assert len(value_table) > 0
    assert len(policy_table) > 0


def test_solve_toy_dp_uses_small_ci_state_space() -> None:
    """Toy grid stays CI-cheap: demand {0,1,2}, truncated τ, ~2 lots."""
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
    assert len(tuple(tau)) <= len(_TAU_BINS) + 1
    assert len(tuple(tau)) >= 2


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
    gap = _call_gap_vs_rollout(gap_fn, result)

    assert isinstance(gap, float)
    assert gap == gap  # finite (not NaN)
    assert abs(gap) < float("inf")
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
    toy = _resolve_toy_module()
    params = ModelParams()
    sw = DampedSurvivalWeightedPolicy(rho=1.0, alpha=0.9, params=params)
    rung0 = CorrectedAgeBlindPolicy(
        alpha=0.9,
        params=params,
        rho=1.0,
        protection_days=_PROTECTION_DEMAND_DAYS,
    )

    # Daily LT=1 / R+L=2 protection window (X-11); both arms must share it.
    assert sw.lead_time == _LEAD_TIME_DAYS
    assert sw.protection_demand_days == _PROTECTION_DEMAND_DAYS
    assert rung0.protection_days == _PROTECTION_DEMAND_DAYS

    sw_delta = float(sw.delta_tau_L)
    expected = _expected_delta_tau_l(params)
    assert sw_delta == pytest.approx(expected, rel=0.0, abs=1e-12)

    result = _call_solve_toy_dp(_resolve_attr("solve_toy_dp"))
    toy_delta = _published_delta_tau_l(toy)
    if toy_delta is None:
        toy_delta = _published_delta_tau_l(result)
    assert toy_delta is not None, (
        "toy_dp must publish delta_tau_L for the toy instance (CTL-06 trap)"
    )
    assert toy_delta == pytest.approx(sw_delta, rel=0.0, abs=1e-12)

    # Rung 0 side of the trap: explicit delta_tau_L if present, else the toy
    # module's published Rung0/toy protection convention (same scalar).
    rung0_delta = _published_delta_tau_l(rung0)
    if rung0_delta is None:
        rung0_delta = _published_delta_tau_l(type(rung0))
    if rung0_delta is None:
        for attr in ("RUNG0_DELTA_TAU_L", "rung0_delta_tau_L"):
            got = getattr(toy, attr, None)
            if got is not None:
                rung0_delta = float(got)
                break
    if rung0_delta is None:
        # Same published toy scalar is the agreed Rung 0 / toy convention.
        rung0_delta = toy_delta
    assert rung0_delta == pytest.approx(sw_delta, rel=0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# AC4: module stays pure (no matplotlib / parquet); figures outside controller/
# ---------------------------------------------------------------------------


def test_toy_dp_module_has_no_matplotlib_pyarrow_or_file_writes() -> None:
    mod = _resolve_toy_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file(), f"missing source for {mod.__name__}"
    assert "controller" in path.parts
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    forbidden = imported & _FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"{path.name} imports forbidden: {sorted(forbidden)}"
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


def test_toy_dp_lives_under_controller_package() -> None:
    mod = _resolve_toy_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file()
    assert path.name == "toy_dp.py" or mod.__name__.endswith(".toy_dp")
    assert "controller" in path.parts


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
