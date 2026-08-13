"""T-027: corrected age-blind Rung 0 (Nahmias / CTL-05) — expected RED.

Locks a policy that observes **total on-hand only** (+ pipeline), applies a
stationary expected-outdating / mean-survival correction (bar_w), and
``case_round``s the base-stock order. When survival weights are constant
(flat-w fixture), orders must match the survival-weighted base-stock on the
same protection interval Delta tau_L (prep for T-032 beta=1 degeneracy).

Frozen estimator parameters (open question in `.team/specs/T-027.md`):
see module-level fixtures below (CTL-05 / X-12 notes).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.filter.belief import ShelfBelief
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.profit import ProfitCosts, episode_profit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROLLER_PKG = "blueberries_voi.controller"
_CANDIDATE_MODULES = (
    "blueberries_voi.controller.rung0",
    "blueberries_voi.controller.ordering",
    "blueberries_voi.controller",
)
_POLICY_NAMES = (
    "CorrectedAgeBlindPolicy",
    "CorrectedAgeBlindOrderPolicy",
    "Rung0Policy",
)

# ---------------------------------------------------------------------------
# CTL-05 / X-12 fixture lock (outdating-correction estimator parameters)
# ---------------------------------------------------------------------------
# Daily delivery, LT=1 -> protection interval covers **2** days of demand
# (X-11 / X-06 worked example: daily Delta tau_L = 2).
_PROTECTION_DAYS: int = 2
# Mean survival weight under the stationary age distribution (outdating
# correction). Naive age-blind uses 1.0; corrected Rung 0 uses bar_w < 1.
_BAR_W: float = 0.75
# Pipeline weight for pending orders; freeze equal to bar_w so flat-w SW and
# Rung 0 share one scalar.
_PIPE_W: float = 0.75
# Injected F^{-1} of protection-interval demand (avoids NB convolution
# ambiguity until T-028/T-029 lock demand helpers).
_DEMAND_TARGET: float = 64.0
# Rung 0 default damping: undamped (rho=1). Coincidence tests share rho with
# the SW reference so only inventory accounting differs.
_RHO: float = 1.0
_CASE_SIZE: int = 8

_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyarrow", "pyarrow.parquet"})


def _resolve_policy_cls() -> type[Any]:
    last_err: Exception | None = None
    for mod_name in _CANDIDATE_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as exc:
            last_err = exc
            continue
        for name in _POLICY_NAMES:
            found = getattr(mod, name, None)
            if found is not None:
                return cast("type[Any]", found)
    msg = (
        "CorrectedAgeBlindPolicy (or Rung0Policy) must be exported from "
        f"{_CANDIDATE_MODULES} per .team/specs/T-027.md"
    )
    if last_err is not None:
        msg = f"{msg}; last import error: {last_err}"
    pytest.fail(msg, pytrace=False)


def _resolve_policy_module() -> Any:
    """Module that defines the Rung 0 policy (docstring / purity checks)."""
    cls = _resolve_policy_cls()
    return importlib.import_module(cls.__module__)


def _belief(*, lot_counts: list[float], age_index: int = 0) -> ShelfBelief:
    """ShelfBelief fixture; Rung 0 must ignore age mix and use sum(counts)."""
    grid = [0.0, 1.0, 2.0, 3.0, 4.0]
    k = len(grid)
    counts = [float(x) for x in lot_counts]
    margs: list[list[float]] = []
    for _ in counts:
        row = [0.0] * k
        row[int(age_index) % k] = 1.0
        margs.append(row)
    return ShelfBelief(lot_counts=counts, age_marginals=margs, tau_grid=grid)


def _hand_rung0_order(
    *,
    total_on_hand: float,
    pending: dict[int, int],
    bar_w: float = _BAR_W,
    pipe_w: float = _PIPE_W,
    demand_target: float = _DEMAND_TARGET,
    rho: float = _RHO,
    case_size: int = _CASE_SIZE,
) -> int:
    """Hand CTL-05 corrected age-blind base-stock (flat bar_w).

    I = bar_w * N + sum_j q_j * pipe_w
    q = case_round(rho * [demand_target - I]^+)
    """
    inv = float(bar_w) * float(total_on_hand) + sum(
        float(q) * float(pipe_w) for q in pending.values()
    )
    raw = float(rho) * max(0.0, float(demand_target) - inv)
    return case_round(raw, case_size)


def _flat_sw_order(
    *,
    lot_counts: list[float],
    pending: dict[int, int],
    flat_w: float = _BAR_W,
    pipe_w: float = _PIPE_W,
    demand_target: float = _DEMAND_TARGET,
    rho: float = _RHO,
    case_size: int = _CASE_SIZE,
) -> int:
    """Survival-weighted base-stock under constant w (beta=1 / flat fixture).

    When w(tau)=flat_w for every lot, SW inventory collapses to flat_w * N +
    pipeline — identical to corrected age-blind with bar_w = flat_w.
    """
    return _hand_rung0_order(
        total_on_hand=float(sum(float(x) for x in lot_counts)),
        pending=pending,
        bar_w=flat_w,
        pipe_w=pipe_w,
        demand_target=demand_target,
        rho=rho,
        case_size=case_size,
    )


def _make_policy(**overrides: Any) -> Any:
    cls = _resolve_policy_cls()
    kwargs: dict[str, Any] = {
        "alpha": 0.9,
        "params": ModelParams(case_size=_CASE_SIZE),
        "rho": _RHO,
        "mean_survival_weight": _BAR_W,
        "pipeline_weight": _PIPE_W,
        "demand_target": _DEMAND_TARGET,
        "protection_days": _PROTECTION_DAYS,
        "case_size": _CASE_SIZE,
    }
    kwargs.update(overrides)
    sig = inspect.signature(cls.__init__)
    names = set(sig.parameters)
    remapped: dict[str, Any] = {}
    aliases = {
        "mean_survival_weight": (
            "mean_survival_weight",
            "bar_w",
            "w_bar",
            "outdating_weight",
        ),
        "pipeline_weight": ("pipeline_weight", "pipe_w", "pipeline_w"),
        "demand_target": (
            "demand_target",
            "demand_quantile",
            "fractile_demand",
        ),
        "protection_days": (
            "protection_days",
            "protection_horizon",
            "delta_tau_l_days",
        ),
    }
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    for key, value in kwargs.items():
        if key in names:
            remapped[key] = value
            continue
        for alt in aliases.get(key, ()):
            if alt in names:
                remapped[alt] = value
                break
        else:
            if accepts_var_kw:
                remapped[key] = value
    return cls(**remapped)


def _invoke_order(
    policy: Any,
    belief: Any,
    *,
    day: int = 0,
    pending_orders: dict[int, int] | None = None,
) -> int:
    """Call order(...) with T-024 Policy surface: day, belief, pending."""
    pending = dict(pending_orders or {})
    sig = inspect.signature(policy.order)
    params = list(sig.parameters.values())
    # Prefer (day, belief, *, pending_orders=) — closed-loop driver convention.
    if len(params) >= 2 and params[0].name in {"day", "t", "t_day"}:
        return int(policy.order(day, belief, pending_orders=pending))
    # Alternate (belief, *, day=, pending_orders=) as in ConstantOrderPolicy.
    return int(policy.order(belief, day=day, pending_orders=pending))


# --- AC: Rung 0 from total on-hand (+ pipeline) with outdating correction ---


def test_rung0_module_docstring_references_nahmias_and_ctl05() -> None:
    mod = _resolve_policy_module()
    doc = (mod.__doc__ or "").lower()
    assert "nahmias" in doc, "module docstring must reference Nahmias"
    assert "ctl-05" in doc or "ctl05" in doc or "rung 0" in doc, (
        "module docstring must reference CTL-05 / Rung 0"
    )
    assert "outdat" in doc or "survival" in doc or "bar" in doc or "mean" in doc, (
        "module docstring must document the expected-outdating / mean-survival "
        "correction formula"
    )


def test_rung0_order_matches_hand_table_total_on_hand_plus_pipeline() -> None:
    """AC: orders from total on-hand (+ pipeline) with bar_w correction."""
    policy = _make_policy()
    fixtures: tuple[tuple[list[float], dict[int, int], int], ...] = (
        # N=40, no pipeline -> I=30 -> raw=34 -> case_round 32
        ([40.0], {}, 32),
        ([10.0, 30.0], {}, 32),
        # N=40 + pending 16 -> I=30+12=42 -> raw=22 -> 24
        ([40.0], {1: 16}, 24),
        ([20.0, 20.0], {1: 8, 2: 8}, 24),
        # Overstocked -> 0
        ([100.0], {}, 0),
        # Empty shelf -> I=0 -> raw=64 -> 64
        ([], {}, 64),
        ([0.0], {1: 0}, 64),
    )
    for lots, pending, expected in fixtures:
        if lots:
            belief = _belief(lot_counts=lots)
        else:
            belief = ShelfBelief(
                lot_counts=[],
                age_marginals=[],
                tau_grid=[0.0, 1.0],
            )
        got = _invoke_order(policy, belief, pending_orders=pending)
        hand = _hand_rung0_order(
            total_on_hand=float(sum(lots)),
            pending=pending,
        )
        assert hand == expected, f"hand table drift: {lots=} {pending=} -> {hand}"
        assert got == expected, (
            f"Rung 0 order {got} != expected {expected} "
            f"for lots={lots} pending={pending}"
        )
        assert got % _CASE_SIZE == 0
        assert isinstance(got, int)


def test_rung0_ignores_age_mix_same_total_on_hand() -> None:
    """Age-blind: same total N + pipeline => same order regardless of ages."""
    policy = _make_policy()
    pending = {1: 8}
    young = _belief(lot_counts=[16.0, 24.0], age_index=0)
    old = _belief(lot_counts=[16.0, 24.0], age_index=4)
    mixed = ShelfBelief(
        lot_counts=[16.0, 24.0],
        age_marginals=[
            [1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        tau_grid=[0.0, 1.0, 2.0, 3.0, 4.0],
    )
    orders = {
        _invoke_order(policy, young, pending_orders=pending),
        _invoke_order(policy, old, pending_orders=pending),
        _invoke_order(policy, mixed, pending_orders=pending),
    }
    assert len(orders) == 1
    assert orders.pop() == _hand_rung0_order(total_on_hand=40.0, pending=pending)


def test_rung0_outdating_correction_differs_from_naive_bar_w_one() -> None:
    """bar_w correction is material vs naive age-blind (bar_w=1)."""
    lots = [40.0]
    pending: dict[int, int] = {}
    corrected = _make_policy(
        mean_survival_weight=_BAR_W,
        pipeline_weight=_PIPE_W,
    )
    naive = _make_policy(mean_survival_weight=1.0, pipeline_weight=1.0)
    belief = _belief(lot_counts=lots)
    q_corr = _invoke_order(corrected, belief, pending_orders=pending)
    q_naive = _invoke_order(naive, belief, pending_orders=pending)
    assert q_corr == _hand_rung0_order(
        total_on_hand=40.0,
        pending=pending,
        bar_w=_BAR_W,
    )
    assert q_naive == _hand_rung0_order(
        total_on_hand=40.0,
        pending=pending,
        bar_w=1.0,
    )
    assert q_corr != q_naive


def test_rung0_documents_protection_interval_lt1_daily() -> None:
    """Protection interval locked to daily LT=1 / Delta tau_L = 2 days."""
    policy = _make_policy()
    days = getattr(policy, "protection_days", None)
    if days is None:
        days = getattr(policy, "protection_horizon", None)
    if days is None:
        days = getattr(policy, "delta_tau_l_days", None)
    assert days == _PROTECTION_DAYS, (
        f"Rung 0 must use protection_days={_PROTECTION_DAYS} (daily LT=1); got {days}"
    )
    mod = _resolve_policy_module()
    doc = (mod.__doc__ or "").lower()
    assert "protection" in doc or "delta" in doc, (
        "module docstring must document the protection-interval convention"
    )


# --- AC: flat-w coincidence with survival-weighted policy ---


def test_rung0_coincides_with_flat_survival_weighted_hand_table() -> None:
    """When w is constant, Rung 0 == SW base-stock after case_round."""
    policy = _make_policy()
    cases: tuple[tuple[list[float], dict[int, int]], ...] = (
        ([40.0], {}),
        ([10.0, 15.0, 15.0], {1: 16}),
        ([8.0, 8.0], {1: 8, 2: 8}),
        ([0.0], {}),
        ([96.0], {1: 24}),
    )
    for lots, pending in cases:
        belief = _belief(lot_counts=lots)
        rung0 = _invoke_order(policy, belief, pending_orders=pending)
        sw = _flat_sw_order(lot_counts=lots, pending=pending)
        assert rung0 == sw, (
            f"flat-w degeneracy failed: Rung0={rung0} SW={sw} "
            f"lots={lots} pending={pending}"
        )


def test_rung0_coincides_with_damped_sw_policy_when_available() -> None:
    """If T-028 SW policy is importable, assert exact int match under flat w.

    Uses the same (rho, demand_target, protection_days) so only inventory
    accounting is compared — prep for T-032 beta=1 gate.
    """
    sw_cls: type[Any] | None = None
    for mod_name in (
        "blueberries_voi.controller.sw_policy",
        "blueberries_voi.controller.ordering",
        "blueberries_voi.controller",
    ):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for name in ("DampedSurvivalWeightedPolicy", "SurvivalWeightedPolicy"):
            found = getattr(mod, name, None)
            if found is not None:
                sw_cls = found
                break
        if sw_cls is not None:
            break
    if sw_cls is None:
        pytest.skip(
            "T-028 SW policy not yet on this branch; hand flat-w table covers AC"
        )

    rho = 0.8
    rung0 = _make_policy(rho=rho)
    sig = inspect.signature(sw_cls.__init__)
    sw_kwargs: dict[str, Any] = {
        "rho": rho,
        "alpha": 0.9,
        "params": ModelParams(case_size=_CASE_SIZE),
        "demand_target": _DEMAND_TARGET,
        "protection_days": _PROTECTION_DAYS,
        "case_size": _CASE_SIZE,
    }
    filtered = {k: v for k, v in sw_kwargs.items() if k in sig.parameters}
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        filtered = sw_kwargs
    sw_policy = sw_cls(**filtered)

    belief = _belief(lot_counts=[20.0, 20.0], age_index=0)
    pending = {1: 16}
    sw_order = _invoke_order(sw_policy, belief, pending_orders=pending)
    flat = _flat_sw_order(lot_counts=[20.0, 20.0], pending=pending, rho=rho)
    if sw_order != flat:
        pytest.skip(
            "SW policy present but not in flat-w / injectable-demand mode; "
            "hand table remains the T-027 AC lock"
        )
    assert _invoke_order(rung0, belief, pending_orders=pending) == sw_order


# --- AC: case_round via T-026 ---


def test_rung0_returns_case_rounded_multiple() -> None:
    policy = _make_policy()
    belief = _belief(lot_counts=[33.0])
    pending = {1: 5}
    got = _invoke_order(policy, belief, pending_orders=pending)
    assert got >= 0
    assert got % _CASE_SIZE == 0
    assert got == _hand_rung0_order(total_on_hand=33.0, pending=pending)


@pytest.mark.parametrize(
    ("demand_target", "total", "pending", "expected"),
    [
        (12.0, 0.0, {}, 16),  # 12 -> nearest 16 (tie 8<->16 -> 16)
        (4.0, 0.0, {}, 8),  # 4.0 tie 0<->8 -> 8
        (3.0, 0.0, {}, 0),
        (20.0, 0.0, {}, 24),  # 20 tie 16<->24 -> 24
        (30.0, 40.0, {}, 0),  # I=30, target 30 -> 0
        (31.0, 40.0, {}, 0),  # I=30, raw=1 -> 0
        (34.0, 40.0, {}, 8),  # I=30, raw=4 -> 8 (tie)
    ],
)
def test_rung0_case_round_boundaries(
    demand_target: float,
    total: float,
    pending: dict[int, int],
    expected: int,
) -> None:
    policy = _make_policy(demand_target=demand_target)
    belief = _belief(lot_counts=[total] if total > 0 else [0.0])
    got = _invoke_order(policy, belief, pending_orders=pending)
    assert got == expected
    assert got == _hand_rung0_order(
        total_on_hand=total,
        pending=pending,
        demand_target=demand_target,
    )


# --- AC: closed-loop smoke + T-025 profit ---


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T027-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def test_rung0_closed_loop_smoke_with_profit_scores() -> None:
    """Short T-024 closed-loop + T-025 episode_profit runs without error."""
    from blueberries_voi.sim.episode import run_closed_loop_episode

    policy = _make_policy()
    log = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=_CASE_SIZE),
        root_seed=27,
        run_id="t027",
        n_burn=1,
        n_score=3,
        lead_time=1,
    )
    assert len(log.days) == 4
    for day in log.days:
        assert day.order_qty >= 0
        assert day.order_qty % _CASE_SIZE == 0
    costs = ProfitCosts(unit_margin=2.0, waste_cost=1.5, stockout_penalty=3.0)
    profit = episode_profit(log, costs)
    assert isinstance(profit, float)
    assert math.isfinite(profit)


# --- Package surface / purity ---


def test_controller_exports_rung0_policy() -> None:
    cls = _resolve_policy_cls()
    pkg = importlib.import_module(_CONTROLLER_PKG)
    exported = getattr(pkg, "__all__", None)
    assert isinstance(exported, list)
    assert exported, "controller.__all__ must list Rung 0 policy"
    names = set(exported)
    assert names & set(_POLICY_NAMES), f"expected one of {_POLICY_NAMES} in {exported}"
    attr_name = next(n for n in _POLICY_NAMES if n in names)
    assert getattr(pkg, attr_name, None) is cls


def test_rung0_module_has_no_matplotlib_pyarrow_or_file_writes() -> None:
    mod = _resolve_policy_module()
    path = Path(mod.__file__ or "")
    assert path.is_file()
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


def test_rung0_order_signature_accepts_day_belief_pending() -> None:
    policy = _make_policy()
    sig = inspect.signature(policy.order)
    names = set(sig.parameters)
    assert "pending_orders" in names
    belief = _belief(lot_counts=[8.0])
    out = _invoke_order(policy, belief, day=2, pending_orders={1: 8})
    assert isinstance(out, int)
    assert out >= 0
