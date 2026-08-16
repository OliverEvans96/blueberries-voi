"""T-081: day-indexed controllers under CAL-01 MWF schedule (CAL-A3) - RED.

Locks ``.team/specs/T-081.md``, ADR 0112 (re-derive #1-2), ADR 0114
(``protection_days`` 3/3/4), ADR 0116 (homogeneous μ + varying length OK
before T-082 / B4):

* ``damped_sw`` uses ``OrderSchedule.protection_days(day)`` (or injected
  callable) - not scalar ``PROTECTION_DEMAND_DAYS=2`` - on order days
* Sun / Tue / Thu protection lengths are 3 / 3 / 4
* Rung 0 / age-blind survival weight is day-indexed (periodic), not
  scalar-only as the production default under the CAL schedule
* ``alpha_tune`` accepts or computes day-indexed protection coverage
* Controllers place no conceptual orders on non-order days (T-079-consistent)
* Homogeneous-μ path is documented for the later B4 / T-084 upgrade
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from scipy.stats import nbinom

from blueberries_voi.filter.belief import shelf_belief_from_oracle
from blueberries_voi.model import ModelParams
from blueberries_voi.sim.bakeoff_ordering import case_round
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule

_EPOCH = date(2024, 1, 1)
_ALPHA = 0.9
_RHO = 1.0
_F_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
_FRESH_ROW = [0.0, 0.0, 0.0, 0.0, 1.0]

# Epoch-aligned order days (ADR 0114): Sun=6, Tue=1, Thu=3 → protection 3/3/4
_ORDER_DAY_PROTECTION: tuple[tuple[int, int, str], ...] = (
    (6, 3, "Sunday"),
    (1, 3, "Tuesday"),
    (3, 4, "Thursday"),
)
_NON_ORDER_DAYS: tuple[tuple[int, str], ...] = (
    (0, "Monday"),
    (2, "Wednesday"),
    (4, "Friday"),
    (5, "Saturday"),
)


def _weekday(day: int) -> int:
    return (_EPOCH + timedelta(days=day)).weekday()


def _empty_belief() -> Any:
    return shelf_belief_from_oracle(
        lot_counts=[0],
        f_marginals=[_FRESH_ROW],
        f_grid=list(_F_GRID),
    )


def _belief_with_total(n: float) -> Any:
    return shelf_belief_from_oracle(
        lot_counts=[float(n)],
        f_marginals=[_FRESH_ROW],
        f_grid=list(_F_GRID),
    )


def _homogeneous_protection_quantile(
    alpha: float, params: ModelParams, protection_days: int
) -> float:
    """F^{-1} of ``protection_days`` i.i.d. daily NB (homogeneous μ; ADR 0116)."""
    if not 0.0 < float(alpha) < 1.0:
        msg = f"alpha must be in (0, 1), got {alpha}"
        raise ValueError(msg)
    r = float(params.nb_r()) * float(protection_days)
    p = float(params.nb_p())
    return float(nbinom.ppf(alpha, r, p))


def _expected_empty_shelf_order(protection_days: int, params: ModelParams) -> int:
    d_star = _homogeneous_protection_quantile(_ALPHA, params, protection_days)
    return int(case_round(_RHO * max(0.0, d_star), params.case_size))


# ---------------------------------------------------------------------------
# Policy resolution / invocation helpers (flexible CAL-A3 surfaces)
# ---------------------------------------------------------------------------


def _sw_cls() -> Any:
    from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy

    return DampedSurvivalWeightedPolicy


def _rung0_cls() -> Any:
    from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy

    return CorrectedAgeBlindPolicy


def _ctor_kwargs(cls: Any, desired: dict[str, Any]) -> dict[str, Any]:
    """Pass only kwargs the constructor accepts (plus ``**kwargs`` if present)."""
    sig = inspect.signature(cls.__init__)
    names = set(sig.parameters) - {"self"}
    accepts_var = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    out: dict[str, Any] = {}
    for key, value in desired.items():
        if key in names or accepts_var:
            out[key] = value
    return out


def _make_sw(
    *,
    params: ModelParams | None = None,
    schedule: OrderSchedule | None = DEFAULT_ORDER_SCHEDULE,
    **overrides: Any,
) -> Any:
    cls = _sw_cls()
    desired: dict[str, Any] = {
        "rho": _RHO,
        "alpha": _ALPHA,
        "params": params or ModelParams(),
    }
    if schedule is not None:
        desired["schedule"] = schedule
    desired.update(overrides)
    return cls(**_ctor_kwargs(cls, desired))


def _make_rung0(
    *,
    params: ModelParams | None = None,
    schedule: OrderSchedule | None = DEFAULT_ORDER_SCHEDULE,
    **overrides: Any,
) -> Any:
    cls = _rung0_cls()
    p = params or ModelParams(case_size=8)
    desired: dict[str, Any] = {
        "alpha": _ALPHA,
        "params": p,
        "rho": _RHO,
        "case_size": int(p.case_size),
        "demand_target": 80.0,
        "mean_survival_weight": 0.75,
        "pipeline_weight": 0.75,
    }
    if schedule is not None:
        desired["schedule"] = schedule
    desired.update(overrides)
    return cls(**_ctor_kwargs(cls, desired))


def _invoke_order(
    policy: Any,
    belief: Any,
    *,
    day: int,
    pending_orders: Mapping[int, int] | None = None,
    schedule: OrderSchedule | None = None,
) -> int:
    pending: Mapping[int, int] = {} if pending_orders is None else pending_orders
    sig = inspect.signature(policy.order)
    names = list(sig.parameters.keys())
    kwargs: dict[str, Any] = {}
    if "pending_orders" in sig.parameters:
        kwargs["pending_orders"] = pending
    if "schedule" in sig.parameters and schedule is not None:
        kwargs["schedule"] = schedule
    if names and names[0] == "day":
        return int(policy.order(day, belief, **kwargs))
    if "day" in sig.parameters:
        return int(policy.order(belief, day=day, **kwargs))
    msg = (
        f"{type(policy).__name__}.order must accept day "
        "(positional or keyword) for day-indexed protection / weights"
    )
    raise AssertionError(msg)


# ---------------------------------------------------------------------------
# AC: damped_sw uses schedule protection_days → 3/3/4 (not scalar 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "expected_days", "label"),
    _ORDER_DAY_PROTECTION,
)
def test_damped_sw_empty_shelf_order_matches_day_indexed_protection(
    day: int, expected_days: int, label: str
) -> None:
    """On Sun/Tue/Thu, SW quantile uses 3/3/4 homogeneous-μ days — not scalar 2."""
    params = ModelParams()
    belief = _empty_belief()
    schedule = DEFAULT_ORDER_SCHEDULE
    assert schedule.can_order(day) is True
    assert schedule.protection_days(day) == expected_days, (
        f"fixture: {label} day={day} must have protection_days={expected_days}"
    )

    policy = _make_sw(params=params, schedule=schedule)
    got = _invoke_order(policy, belief, day=day, pending_orders={}, schedule=schedule)

    expected = _expected_empty_shelf_order(expected_days, params)
    scalar_two = _expected_empty_shelf_order(2, params)
    assert expected != scalar_two, "hand table must distinguish 3/4-day from daily-2"
    assert got == expected, (
        f"damped_sw on {label} (day={day}) must use protection_days={expected_days} "
        f"(order {expected}); got {got} — scalar PROTECTION_DEMAND_DAYS=2 yields "
        f"{scalar_two} (ADR 0112 / T-081)"
    )
    assert got != scalar_two, (
        f"damped_sw still uses scalar 2-day protection on {label} "
        f"(order={got}); must consult OrderSchedule.protection_days(day)"
    )


def test_damped_sw_sun_tue_thu_protection_lengths_are_3_3_4() -> None:
    """Unit/integration: protection lengths used on order days are 3 / 3 / 4."""
    params = ModelParams()
    belief = _empty_belief()
    schedule = DEFAULT_ORDER_SCHEDULE
    policy = _make_sw(params=params, schedule=schedule)

    lengths: list[int] = []
    for day, expected_days, label in _ORDER_DAY_PROTECTION:
        got_order = _invoke_order(
            policy, belief, day=day, pending_orders={}, schedule=schedule
        )
        # Infer length from which homogeneous quantile matches the order.
        matched: int | None = None
        for candidate in (2, 3, 4, 5):
            if got_order == _expected_empty_shelf_order(candidate, params):
                matched = candidate
                break
        assert matched == expected_days, (
            f"{label} day={day}: expected protection length {expected_days}, "
            f"inferred {matched} from order={got_order} "
            f"(2-day scalar would be {_expected_empty_shelf_order(2, params)})"
        )
        lengths.append(matched)
    assert lengths == [3, 3, 4]


def test_damped_sw_accepts_schedule_or_protection_days_callable() -> None:
    """Interfaces: schedule and/or ``protection_days`` callable injectable."""
    cls = _sw_cls()
    sig = inspect.signature(cls.__init__)
    names = set(sig.parameters)
    accepts_var = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    has_schedule = "schedule" in names or accepts_var
    has_callable_prot = "protection_days" in names or accepts_var
    assert has_schedule or has_callable_prot, (
        "DampedSurvivalWeightedPolicy must accept schedule=OrderSchedule and/or "
        "protection_days: int | Callable[[int], int] per T-081 Interfaces"
    )

    # Callable path: force a distinctive 5-day cover on every day.
    params = ModelParams()
    belief = _empty_belief()
    five_day = _expected_empty_shelf_order(5, params)
    if "protection_days" in names or accepts_var:
        policy = _make_sw(
            params=params,
            schedule=None,
            protection_days=lambda _day: 5,
        )
        got = _invoke_order(policy, belief, day=6, pending_orders={})
        assert got == five_day, (
            "injected protection_days callable must drive the SW quantile "
            f"(expected {five_day}, got {got})"
        )


# ---------------------------------------------------------------------------
# AC: Rung 0 / age-blind survival weight is day-indexed (not scalar-only)
# ---------------------------------------------------------------------------


def _survival_weight_resolver(
    policy: Any,
) -> Callable[[int], float] | None:
    """Locate a day→weight API; None if only a scalar float remains."""
    for attr in (
        "mean_survival_weight_for_day",
        "survival_weight_for_day",
        "bar_w_for_day",
        "age_blind_weight_for_day",
    ):
        fn = getattr(policy, attr, None)
        if callable(fn):

            def _from_attr(day: int, _fn: Any = fn) -> float:
                return float(_fn(day))

            return _from_attr

    w = getattr(policy, "mean_survival_weight", None)
    if callable(w):

        def _from_callable(day: int, _w: Any = w) -> float:
            return float(_w(day))

        return _from_callable
    if isinstance(w, Mapping):

        def _from_map(day: int, _m: Mapping[Any, Any] = w) -> float:
            if day in _m:
                return float(_m[day])
            wd = _weekday(day)
            if wd in _m:
                return float(_m[wd])
            msg = f"day-indexed weight map missing day={day} / weekday={wd}"
            raise KeyError(msg)

        return _from_map

    for attr in (
        "survival_weights_by_weekday",
        "mean_survival_weights",
        "bar_w_by_weekday",
        "periodic_survival_weights",
    ):
        table = getattr(policy, attr, None)
        if isinstance(table, Mapping):

            def _from_table(
                day: int,
                _t: Mapping[Any, Any] = table,
                _attr: str = attr,
            ) -> float:
                wd = _weekday(day)
                if wd in _t:
                    return float(_t[wd])
                if day in _t:
                    return float(_t[day])
                msg = f"{_attr} missing weekday={wd}"
                raise KeyError(msg)

            return _from_table
    return None


def test_rung0_accepts_day_indexed_survival_weight_and_uses_day() -> None:
    """Injected weekday→bar_w must change orders by day (same on-hand)."""
    # Higher bar_w → higher effective inventory → smaller order.
    weights_by_weekday = {
        0: 0.40,
        1: 0.55,  # Tue
        2: 0.60,
        3: 0.90,  # Thu
        4: 0.70,
        5: 0.80,
        6: 0.45,  # Sun
    }
    params = ModelParams(case_size=8)
    belief = _belief_with_total(40.0)
    demand_target = 100.0

    attempts: tuple[dict[str, Any], ...] = (
        {"mean_survival_weight": weights_by_weekday},
        {"survival_weights_by_weekday": weights_by_weekday},
        {"mean_survival_weights": weights_by_weekday},
        {"bar_w_by_weekday": weights_by_weekday},
        {"periodic_survival_weights": weights_by_weekday},
        {"mean_survival_weight": (lambda d: float(weights_by_weekday[_weekday(d)]))},
    )
    policy: Any | None = None
    resolver: Callable[[int], float] | None = None
    errors: list[str] = []
    for extra in attempts:
        try:
            cand = _make_rung0(
                params=params,
                schedule=DEFAULT_ORDER_SCHEDULE,
                demand_target=demand_target,
                pipeline_weight=0.0,
                rho=1.0,
                **extra,
            )
        except (TypeError, ValueError) as exc:
            errors.append(f"{sorted(extra)!r}: {exc}")
            continue
        cand_resolver = _survival_weight_resolver(cand)
        if cand_resolver is not None:
            policy = cand
            resolver = cand_resolver
            break
        errors.append(f"{sorted(extra)!r}: constructed but no day→weight API")

    assert policy is not None and resolver is not None, (
        "CorrectedAgeBlindPolicy must accept day-indexed survival weights "
        "(Mapping/Callable or weekday table) — scalar-only bar_w remains "
        f"(ADR 0112 re-derive #2 / T-081); attempts: {errors}"
    )

    q_sun = _invoke_order(policy, belief, day=6, pending_orders={})
    q_tue = _invoke_order(policy, belief, day=1, pending_orders={})
    q_thu = _invoke_order(policy, belief, day=3, pending_orders={})
    assert q_sun != q_thu or q_sun != q_tue, (
        "day-indexed bar_w must change Rung0 orders across Sun/Tue/Thu for "
        f"the same on-hand; got sun={q_sun} tue={q_tue} thu={q_thu} "
        "(policy still ignores day / uses a single scalar)"
    )
    # Sun bar_w=0.45 < Thu bar_w=0.90 → Sun orders more.
    assert q_sun > q_thu, (
        f"lower Sunday bar_w must yield larger order than Thursday "
        f"(got sun={q_sun}, thu={q_thu})"
    )


def test_rung0_cal_schedule_default_is_not_scalar_only_survival_weight() -> None:
    """Production default under CAL-01 schedule must not be float-only + ignore day."""
    policy = _make_rung0(schedule=DEFAULT_ORDER_SCHEDULE)
    resolver = _survival_weight_resolver(policy)
    assert resolver is not None, (
        "Under DEFAULT_ORDER_SCHEDULE, Rung0 production path still exposes only "
        "a scalar mean_survival_weight and discards day — age-blind weight must "
        "be day-indexed / periodic (ADR 0011/0109; T-081)"
    )
    # Smoke: resolver is callable for at least one order day and one non-order day.
    for day, _label in ((6, "Sunday"), (0, "Monday")):
        w = resolver(day)
        assert 0.0 < float(w) <= 1.0, (
            f"day-indexed survival weight on day={day} must be in (0, 1]; got {w}"
        )


# ---------------------------------------------------------------------------
# AC: alpha_tune accepts / computes day-indexed protection coverage
# ---------------------------------------------------------------------------


def _alpha_tune_module() -> Any:
    return importlib.import_module("blueberries_voi.sim.alpha_tune")


def test_alpha_tune_exposes_or_computes_day_indexed_protection_coverage() -> None:
    """T-083 retune needs day-indexed coverage (3/3/4), not a frozen scalar 2."""
    mod = _alpha_tune_module()
    schedule = DEFAULT_ORDER_SCHEDULE

    helper: Callable[[int], int] | None = None
    for name in (
        "protection_coverage_days",
        "protection_days_for_day",
        "day_indexed_protection_days",
        "protection_demand_days_for_day",
        "protection_days_for_tune",
    ):
        fn = getattr(mod, name, None)
        if callable(fn):
            helper = fn
            break

    if helper is None:
        # Fallback: public quantile helper must accept a day-varying length.
        q_fn = getattr(mod, "protection_demand_quantile", None)
        if q_fn is None:
            q_fn = getattr(mod, "_protection_demand_quantile", None)
        if q_fn is not None:
            sig = inspect.signature(q_fn)
            day_aware = any(
                n in sig.parameters
                for n in (
                    "protection_days",
                    "days",
                    "n_days",
                    "day",
                    "schedule",
                )
            )
            assert day_aware, (
                "alpha_tune protection quantile helper must accept "
                "protection_days/day/schedule for day-indexed coverage "
                f"(signature={sig})"
            )
            params = ModelParams()
            for day, expected_days, label in _ORDER_DAY_PROTECTION:
                kwargs: dict[str, Any] = {}
                if "protection_days" in sig.parameters:
                    kwargs["protection_days"] = expected_days
                elif "days" in sig.parameters:
                    kwargs["days"] = expected_days
                elif "n_days" in sig.parameters:
                    kwargs["n_days"] = expected_days
                elif "day" in sig.parameters:
                    kwargs["day"] = day
                elif "schedule" in sig.parameters:
                    kwargs["schedule"] = schedule
                    # day may still be required positionally / kw
                    if "day" in sig.parameters:
                        kwargs["day"] = day
                got_q = float(q_fn(_ALPHA, params, **kwargs))
                want_q = _homogeneous_protection_quantile(_ALPHA, params, expected_days)
                assert got_q == pytest.approx(want_q, rel=0.0, abs=1e-9), (
                    f"alpha_tune quantile on {label} must use {expected_days}-day "
                    f"homogeneous cover; got {got_q} vs {want_q}"
                )
            return

        pytest.fail(
            "alpha_tune must expose day-indexed protection coverage "
            "(helper returning 3/3/4, or quantile fn accepting protection_days/"
            "day/schedule) so T-083 can retune gates — currently scalar "
            "_PROTECTION_DEMAND_DAYS=2 only"
        )

    for day, expected_days, label in _ORDER_DAY_PROTECTION:
        got = int(helper(day))
        assert got == expected_days, (
            f"alpha_tune coverage helper on {label} day={day}: "
            f"expected {expected_days}, got {got}"
        )


def test_alpha_tune_documents_day_indexed_protection_for_t083() -> None:
    mod = _alpha_tune_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file()
    text = path.read_text(encoding="utf-8").lower()
    doc = (mod.__doc__ or "").lower()
    blob = text + "\n" + doc
    mentions_day_index = (
        "day-index" in blob
        or "day_index" in blob
        or "protection_days" in blob
        or "3/3/4" in blob
        or "order schedule" in blob
        or "orderschedule" in blob
    )
    assert mentions_day_index, (
        "sim/alpha_tune.py must document day-indexed protection coverage "
        "for T-083 retune (CAL-A3 / T-081)"
    )


# ---------------------------------------------------------------------------
# AC: controllers place no conceptual orders on non-order days
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("day", "label"), _NON_ORDER_DAYS)
def test_damped_sw_returns_zero_on_non_order_days(day: int, label: str) -> None:
    schedule = DEFAULT_ORDER_SCHEDULE
    assert schedule.can_order(day) is False
    params = ModelParams()
    belief = _empty_belief()
    policy = _make_sw(params=params, schedule=schedule)
    got = _invoke_order(policy, belief, day=day, pending_orders={}, schedule=schedule)
    assert got == 0, (
        f"damped_sw must not place a conceptual order on {label} "
        f"(day={day}, weekday={_weekday(day)}); got {got} "
        "(consistent with T-079 OrderSchedule gate)"
    )


@pytest.mark.parametrize(("day", "label"), _NON_ORDER_DAYS)
def test_rung0_returns_zero_on_non_order_days(day: int, label: str) -> None:
    schedule = DEFAULT_ORDER_SCHEDULE
    assert schedule.can_order(day) is False
    policy = _make_rung0(
        schedule=schedule,
        demand_target=100.0,
        mean_survival_weight=0.5,
        pipeline_weight=0.0,
    )
    belief = _belief_with_total(0.0)
    got = _invoke_order(policy, belief, day=day, pending_orders={}, schedule=schedule)
    assert got == 0, (
        f"Rung0 must not place a conceptual order on {label} "
        f"(day={day}); got {got} (T-079-consistent / T-081)"
    )


# ---------------------------------------------------------------------------
# AC: homogeneous-μ path documented for T-084 / B4 upgrade
# ---------------------------------------------------------------------------


def test_day_indexed_controllers_document_homogeneous_mu_path_for_b4() -> None:
    """Varying protection length + homogeneous μ is allowed until B4 (ADR 0116)."""
    blobs: list[str] = []
    for mod_name in (
        "blueberries_voi.sim.bakeoff_damped_sw",
        "blueberries_voi.controller.rung0",
        "blueberries_voi.sim.alpha_tune",
    ):
        mod = importlib.import_module(mod_name)
        path = Path(inspect.getsourcefile(mod) or "")
        if path.is_file():
            blobs.append(path.read_text(encoding="utf-8"))
        blobs.append(mod.__doc__ or "")

    text = "\n".join(blobs).lower()
    # Explicit CAL-A3 wording; bare "i.i.d." in legacy daily docs is not enough.
    mentions_homogeneous = (
        "homogeneous" in text
        or "homogenous" in text  # common misspelling tolerance
        or "constant μ" in text
        or "constant mu" in text
        or "homogeneous-μ" in text
        or "homogeneous mu" in text
    )
    mentions_upgrade = (
        "t-084" in text
        or "t084" in text
        or "cal-b4" in text
        or "heterogeneous" in text
        or "day-indexed μ" in text
        or "day-indexed mu" in text
        or "μ(day)" in text
        or "mu(day)" in text
    )
    assert mentions_homogeneous, (
        "controller / alpha_tune path must document homogeneous-μ protection "
        "(day-varying length only) per ADR 0116 / T-081"
    )
    assert mentions_upgrade, (
        "same docs must point at T-084 / B4 (or heterogeneous / μ(day)) upgrade"
    )
