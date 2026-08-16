"""T-028 CTL-01 damped survival-weighted base-stock — RED acceptance contracts.

Locks ADR 0058 (CTL-01=C), ADR 0092 (`ShelfBelief` only), and `.team/specs/T-028.md`
before production policy code exists.

Formula under test (ADR 0058 / T-028):

    q_t = case_round(rho · [F^{-1}_{D_{t:t+L}}(alpha) - Ĩ_t]⁺)

with default rho=0.8, Ĩ_t from T-023 ``effective_inventory`` (MF marginals /
``from_marginals=True``). Legacy no-schedule path uses R+L=2 under daily LT=1;
CAL-01 / ADR 0112 base case is MWF day-indexed protection (T-081 / T-083).
"""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: Python damped_sw compute removed", allow_module_level=True)

import ast
import importlib
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest
from scipy.stats import nbinom

from blueberries_voi.filter.belief import effective_inventory, shelf_belief_from_oracle
from blueberries_voi.model import ModelParams, q10_age_increment
from blueberries_voi.sim.bakeoff_ordering import case_round

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROLLER_PKG = "blueberries_voi.controller"
_POLICY_ATTR = "DampedSurvivalWeightedPolicy"
_POLICY_MODULE_CANDIDATES = (
    "blueberries_voi.sim.bakeoff_damped_sw",
    "blueberries_voi.controller.sw_base_stock",
    "blueberries_voi.controller.base_stock",
    "blueberries_voi.sim.bakeoff_ordering",
    "blueberries_voi.controller",
)

# LT=1 stays; legacy no-schedule R+L=2 (ADR 0006). MWF base case is day-indexed
# 3/3/4 (ADR 0112 / T-081); T-083 supersedes immutable-daily locks.
_LEAD_TIME_DAYS = 1
_PROTECTION_DEMAND_DAYS = 2
_LEGACY_NO_SCHEDULE_PROTECTION_DAYS = 2

# Shared oracle belief / pending fixture for the hand-computed order table.
_TABLE_GRID = (0.0, 2.0, 4.0, 6.0)
_TABLE_LOT_COUNTS = (20, 10)
_TABLE_AGES = (0.0, 4.0)
_TABLE_PENDING: dict[int, int] = {1: 8}

# (rho, alpha, expected order qty) under ModelParams() defaults + table belief/pending.
# Ĩ_t and F^{-1} are recomputed in the test so the table stays tied to helpers;
# expected ints were hand-checked against case_round(rho[d* - Ĩ]⁺).
_ORDER_TABLE: tuple[tuple[float, float, int], ...] = (
    (1.0, 0.5, 24),
    (0.8, 0.5, 16),  # rho≠1 damping
    (0.5, 0.5, 8),
    (1.0, 0.8, 32),
    (0.8, 0.8, 24),
    (0.5, 0.8, 16),
    (1.0, 0.9, 40),
    (0.8, 0.9, 32),  # default-rho row
    (0.5, 0.9, 16),
)


def _resolve_policy_class() -> Any:
    """Locate ``DampedSurvivalWeightedPolicy`` on the controller surface."""
    last_err: Exception | None = None
    for name in _POLICY_MODULE_CANDIDATES:
        try:
            mod = importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
        found = getattr(mod, _POLICY_ATTR, None)
        if found is not None:
            return found
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        f"{_POLICY_ATTR} must be exported from controller "
        f"(tried {_POLICY_MODULE_CANDIDATES}) per T-028 / ADR 0058{detail}",
        pytrace=False,
    )


def _policy_defining_module(cls: type) -> Any:
    mod_name = cls.__module__
    return importlib.import_module(mod_name)


def _invoke_order(
    policy: Any,
    belief: Any,
    *,
    day: int = 0,
    pending_orders: Mapping[int, int] | None = None,
) -> int:
    """Call ``order`` under T-024 (day-first) or T-028 sketch (belief-first)."""
    pending: Mapping[int, int] = {} if pending_orders is None else pending_orders
    sig = inspect.signature(policy.order)
    names = list(sig.parameters.keys())
    if names and names[0] == "day":
        return int(policy.order(day, belief, pending_orders=pending))
    if "day" in sig.parameters:
        return int(policy.order(belief, day=day, pending_orders=pending))
    return int(policy.order(belief, pending_orders=pending))


def _protection_demand_quantile(alpha: float, params: ModelParams) -> float:
    """F^{-1} of sum of ``_PROTECTION_DEMAND_DAYS`` i.i.d. daily NB demands.

    Daily NB(r, p) sums to NB(days·r, p) under the scipy ``nbinom`` parameterisation
    used by ``ModelParams.nb_r`` / ``nb_p`` (MOD-09 / MOD-26).
    """
    if not 0.0 < alpha < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    r = float(params.nb_r()) * float(_PROTECTION_DEMAND_DAYS)
    p = float(params.nb_p())
    return float(nbinom.ppf(alpha, r, p))


def _table_belief_and_params() -> tuple[Any, ModelParams]:
    params = ModelParams()
    belief = shelf_belief_from_oracle(
        lot_counts=list(_TABLE_LOT_COUNTS),
        ages=list(_TABLE_AGES),
        tau_grid=list(_TABLE_GRID),
    )
    return belief, params


def _hand_order(
    *,
    rho: float,
    alpha: float,
    belief: Any,
    pending_orders: Mapping[int, int],
    params: ModelParams,
) -> int:
    """Hand-compute case-rounded damped SW order (ADR 0058)."""
    i_tilde = float(
        effective_inventory(belief, pending_orders=pending_orders, params=params)
    )
    d_star = _protection_demand_quantile(alpha, params)
    raw = float(rho) * max(0.0, d_star - i_tilde)
    return int(case_round(raw, params.case_size))


# ---------------------------------------------------------------------------
# AC: policy computes Ĩ via effective_inventory and emits case-rounded orders
# ---------------------------------------------------------------------------


def test_damped_sw_policy_class_is_exportable() -> None:
    cls = _resolve_policy_class()
    assert inspect.isclass(cls)
    assert cls.__name__ == _POLICY_ATTR


def test_damped_sw_order_matches_effective_inventory_plus_case_round() -> None:
    """Ĩ_t must come from T-023 effective_inventory; q via controller case_round."""
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    rho, alpha = 0.8, 0.9
    policy = cls(rho=rho, alpha=alpha, params=params)
    expected = _hand_order(
        rho=rho,
        alpha=alpha,
        belief=belief,
        pending_orders=_TABLE_PENDING,
        params=params,
    )
    got = _invoke_order(policy, belief, pending_orders=_TABLE_PENDING)
    assert isinstance(got, int)
    assert got >= 0
    assert got % params.case_size == 0
    assert got == expected


def test_damped_sw_order_is_multiple_of_case_size() -> None:
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    policy = cls(rho=0.8, alpha=0.8, params=params)
    got = _invoke_order(policy, belief, pending_orders=_TABLE_PENDING)
    assert got % params.case_size == 0


# ---------------------------------------------------------------------------
# AC: fixed fixtures → deterministic hand-computed table (incl. rho≠1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("rho", "alpha", "expected_q"), _ORDER_TABLE)
def test_damped_sw_order_table_matches_hand_computation(
    rho: float, alpha: float, expected_q: int
) -> None:
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    # Sanity: fixture expected ints match the locked hand formula.
    assert (
        _hand_order(
            rho=rho,
            alpha=alpha,
            belief=belief,
            pending_orders=_TABLE_PENDING,
            params=params,
        )
        == expected_q
    )
    policy = cls(rho=rho, alpha=alpha, params=params)
    got = _invoke_order(policy, belief, pending_orders=_TABLE_PENDING)
    assert got == expected_q


def test_damped_sw_orders_are_deterministic_across_repeated_calls() -> None:
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    policy = cls(rho=0.8, alpha=0.9, params=params)
    first = _invoke_order(policy, belief, day=3, pending_orders=_TABLE_PENDING)
    second = _invoke_order(policy, belief, day=3, pending_orders=_TABLE_PENDING)
    third = _invoke_order(policy, belief, day=99, pending_orders=dict(_TABLE_PENDING))
    assert first == second == third


def test_damped_sw_rho_damping_changes_order_vs_undamped() -> None:
    """rho≠1 must change the order when the undamped gap is large (ADR 0058 C)."""
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    undamped = _invoke_order(
        cls(rho=1.0, alpha=0.9, params=params),
        belief,
        pending_orders=_TABLE_PENDING,
    )
    damped = _invoke_order(
        cls(rho=0.8, alpha=0.9, params=params),
        belief,
        pending_orders=_TABLE_PENDING,
    )
    assert undamped == 40
    assert damped == 32
    assert damped < undamped


def test_damped_sw_positive_part_yields_zero_when_inventory_covers_quantile() -> None:
    cls = _resolve_policy_class()
    params = ModelParams()
    belief = shelf_belief_from_oracle(
        lot_counts=[200],
        ages=[0.0],
        tau_grid=list(_TABLE_GRID),
    )
    policy = cls(rho=0.8, alpha=0.9, params=params)
    got = _invoke_order(policy, belief, pending_orders={})
    assert got == 0


def test_damped_sw_empty_shelf_orders_full_damped_quantile() -> None:
    cls = _resolve_policy_class()
    params = ModelParams()
    belief = shelf_belief_from_oracle(
        lot_counts=[0],
        ages=[0.0],
        tau_grid=list(_TABLE_GRID),
    )
    policy = cls(rho=0.8, alpha=0.9, params=params)
    expected = _hand_order(
        rho=0.8,
        alpha=0.9,
        belief=belief,
        pending_orders={},
        params=params,
    )
    assert expected == 56
    assert _invoke_order(policy, belief, pending_orders={}) == expected


# ---------------------------------------------------------------------------
# AC: default rho=0.8; alpha is an explicit constructor argument
# ---------------------------------------------------------------------------


def test_damped_sw_default_rho_is_0_8() -> None:
    cls = _resolve_policy_class()
    sig = inspect.signature(cls.__init__)
    assert "rho" in sig.parameters, "rho must be a constructor parameter"
    assert sig.parameters["rho"].default == 0.8
    belief, params = _table_belief_and_params()
    # Omitting rho must match explicit rho=0.8 on the table fixture.
    defaulted = cls(alpha=0.9, params=params)
    explicit = cls(rho=0.8, alpha=0.9, params=params)
    assert _invoke_order(defaulted, belief, pending_orders=_TABLE_PENDING) == 32
    assert _invoke_order(explicit, belief, pending_orders=_TABLE_PENDING) == 32


def test_damped_sw_alpha_is_required_constructor_argument() -> None:
    cls = _resolve_policy_class()
    sig = inspect.signature(cls.__init__)
    assert "alpha" in sig.parameters
    assert sig.parameters["alpha"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        cls(params=ModelParams())


def test_damped_sw_rho_override_is_honoured() -> None:
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    policy = cls(rho=0.5, alpha=0.9, params=params)
    assert _invoke_order(policy, belief, pending_orders=_TABLE_PENDING) == 16


# ---------------------------------------------------------------------------
# AC: never reads RPF._state; beliefs via shelf_belief_from_* / fixtures
# ---------------------------------------------------------------------------


def test_damped_sw_policy_module_does_not_reference_particle_filter_private_state() -> (
    None
):
    cls = _resolve_policy_class()
    mod = _policy_defining_module(cls)
    source_path = Path(inspect.getsourcefile(mod) or "")
    assert source_path.is_file(), f"missing source for {mod.__name__}"
    source = source_path.read_text(encoding="utf-8")
    assert "ResearchParticleFilter._state" not in source
    tree = ast.parse(source, filename=str(source_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "_state":
            pytest.fail(
                f"{source_path.name} must not access ._state (ADR 0092)",
                pytrace=False,
            )


def test_damped_sw_order_accepts_oracle_shelf_belief_without_particle_filter() -> None:
    """CTL path constructs beliefs via shelf_belief_from_oracle / fixtures only."""
    cls = _resolve_policy_class()
    belief, params = _table_belief_and_params()
    assert type(belief).__name__ == "ShelfBelief"
    policy = cls(rho=0.8, alpha=0.9, params=params)
    got = _invoke_order(policy, belief, pending_orders=_TABLE_PENDING)
    assert got == 32


def test_controller_package_exports_damped_sw_policy() -> None:
    cls = _resolve_policy_class()
    pkg = importlib.import_module(_CONTROLLER_PKG)
    exported = getattr(pkg, "__all__", None)
    assert isinstance(exported, list)
    assert _POLICY_ATTR in exported
    assert getattr(pkg, _POLICY_ATTR, None) is cls


# ---------------------------------------------------------------------------
# AC: LT=1 locked; legacy scalar 2 only without schedule (T-083 supersession)
# ---------------------------------------------------------------------------


def test_damped_sw_protection_interval_lt1_legacy_scalar_not_immutable_base() -> None:
    """LT=1 stays locked; PROTECTION_DEMAND_DAYS=2 is legacy no-schedule only.

    ADR 0112 / T-083: daily R+L=2 is no longer the immutable scientific base
    case — MWF day-indexed protection (3/3/4) is (see T-081).
    """
    from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE

    cls = _resolve_policy_class()
    params = ModelParams()
    policy = cls(rho=0.8, alpha=0.9, params=params)
    lead = getattr(policy, "lead_time", None)
    if lead is None:
        lead = getattr(cls, "LEAD_TIME_DAYS", None)
    if lead is None:
        lead = getattr(cls, "lead_time", None)
    assert lead == _LEAD_TIME_DAYS, (
        "policy must expose lead_time / LEAD_TIME_DAYS == 1 (LT=1)"
    )

    # Legacy constant may remain for no-schedule callers.
    legacy = getattr(cls, "PROTECTION_DEMAND_DAYS", None)
    if legacy is None:
        legacy = getattr(policy, "protection_demand_days", None)
    assert legacy == _LEGACY_NO_SCHEDULE_PROTECTION_DAYS, (
        "legacy PROTECTION_DEMAND_DAYS constant remains 2 for no-schedule path"
    )

    # Base-case path: schedule-aware policy resolves 3/3/4 on order days.
    scheduled = cls(rho=1.0, alpha=0.9, params=params, schedule=DEFAULT_ORDER_SCHEDULE)
    resolve = getattr(scheduled, "_resolve_protection_days", None)
    assert callable(resolve), (
        "schedule-aware SW must expose day-indexed protection resolution (T-081)"
    )
    for day, expected in ((6, 3), (1, 3), (3, 4)):
        assert int(resolve(day)) == expected, (
            f"MWF base case protection on day={day} must be {expected}, "
            f"got {resolve(day)} (not immutable daily 2)"
        )


def test_damped_sw_delta_tau_l_matches_q10_lead_time_increment() -> None:
    """Δτ_L under daily LT=1 equals one calendar day of in-store effective age."""
    cls = _resolve_policy_class()
    params = ModelParams()
    policy = cls(rho=0.8, alpha=0.9, params=params)
    expected = q10_age_increment(
        float(_LEAD_TIME_DAYS),
        t_store_c=params.t_store_c,
        t_ref_c=params.t_ref_c,
        q10=params.q10,
    )
    got = getattr(policy, "delta_tau_L", None)
    if got is None:
        got = getattr(cls, "DELTA_TAU_L", None)
    if got is None:
        got = getattr(policy, "delta_tau_l", None)
    assert got is not None, (
        "policy must expose delta_tau_L (same scalar Rung 0 will share; CTL-06)"
    )
    assert float(got) == pytest.approx(float(expected), rel=0.0, abs=1e-12)


def test_damped_sw_module_documents_protection_interval_and_rung0_parity() -> None:
    cls = _resolve_policy_class()
    mod = _policy_defining_module(cls)
    doc = (mod.__doc__ or "") + "\n" + (cls.__doc__ or "")
    doc_l = doc.lower()
    assert "lead" in doc_l or "lt=1" in doc_l or "lt = 1" in doc_l
    assert "rung" in doc_l or "δτ" in doc.lower() or "delta_tau" in doc_l
    assert "rho" in doc or "rho" in doc_l
    source_path = Path(inspect.getsourcefile(mod) or "")
    assert source_path.is_file()
    # Prefer documentation living under controller/ (pure library; agent brief).
    assert "controller" in source_path.parts


def test_damped_sw_demand_quantile_uses_protection_demand_days() -> None:
    """No-schedule legacy path: F^{-1} uses 2-day NB sum, not a single day.

    MWF base-case day-indexed lengths are locked in T-081 / T-083 tests.
    """
    cls = _resolve_policy_class()
    params = ModelParams()
    belief = shelf_belief_from_oracle(
        lot_counts=[0],
        ages=[0.0],
        tau_grid=list(_TABLE_GRID),
    )
    # Explicitly no schedule → legacy scalar protection window.
    policy = cls(rho=1.0, alpha=0.9, params=params)
    got = _invoke_order(policy, belief, pending_orders={})
    two_day = int(
        case_round(_protection_demand_quantile(0.9, params), params.case_size)
    )
    one_day = int(
        case_round(
            float(nbinom.ppf(0.9, params.nb_r(), params.nb_p())),
            params.case_size,
        )
    )
    assert two_day == 72  # ppf=74 → nearest case 72 under empty Ĩ=0, rho=1
    assert one_day == 40  # ppf=40
    assert got == two_day
    assert got != one_day
