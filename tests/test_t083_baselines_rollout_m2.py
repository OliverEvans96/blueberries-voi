"""T-083 CAL-A4: baselines, rollout Hx7, M2 gates under OrderSchedule - RED.

Locks ``.team/specs/T-083.md`` and ADR 0109 mandatory re-derive #3:

* production rollout horizon presets step in multiples of 7
* ``toy_dp`` certificate is schedule-aware (order-day epochs, not silent daily)
* M2 ladder / ``m2_gates`` run under default ``OrderSchedule`` with day-indexed
  Rung 0 weights (T-081)
* burn-in notes acknowledge **periodic** age under MWF (not daily stationary)
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule

_ROLLOUT_MOD = "blueberries_voi.controller.rollout"
_TOY_MOD = "blueberries_voi.controller.toy_dp"
_GATES_MOD = "blueberries_voi.sim.m2_gates"
_LADDER_MOD = "blueberries_voi.sim.m2_ladder"
_ALPHA_MOD = "blueberries_voi.sim.alpha_tune"
_EPISODE_MOD = "blueberries_voi.sim.episode"
_VOI_SWEEP_MOD = "blueberries_voi.voi.sweep"

# ADR 0109 / T-083: production presets must be weekly-aligned.
_EXPECTED_HORIZON_PRESETS: frozenset[int] = frozenset({7, 14, 21, 28})


def _import(name: str) -> Any:
    return importlib.import_module(name)


def _module_source(mod: Any) -> str:
    path = getattr(mod, "__file__", None)
    assert path is not None, f"{mod!r} must have __file__"
    return Path(path).read_text(encoding="utf-8")


def _combined_docs(*objs: Any) -> str:
    parts: list[str] = []
    for obj in objs:
        parts.append(str(getattr(obj, "__doc__", None) or ""))
    return "\n".join(parts).lower()


# ---------------------------------------------------------------------------
# AC: rollout horizons / defaults are multiples of 7
# ---------------------------------------------------------------------------


def test_default_rollout_horizons_export_multiples_of_seven() -> None:
    """Production preset tuple locks H ∈ {7, 14, …} (ADR 0109 re-derive #3)."""
    mod = _import(_ROLLOUT_MOD)
    horizons = getattr(mod, "DEFAULT_ROLLOUT_HORIZONS", None)
    assert horizons is not None, (
        "controller.rollout must export DEFAULT_ROLLOUT_HORIZONS "
        "(tuple of calendar-day horizons in multiples of 7)"
    )
    assert isinstance(horizons, tuple), "DEFAULT_ROLLOUT_HORIZONS must be a tuple"
    assert horizons, "DEFAULT_ROLLOUT_HORIZONS must be non-empty"
    for h in horizons:
        assert int(h) > 0, f"horizon must be positive, got {h!r}"
        assert int(h) % 7 == 0, (
            f"production rollout horizon {h} must be a multiple of 7 "
            "(weekly periodicity under MWF)"
        )
    assert _EXPECTED_HORIZON_PRESETS.issubset({int(h) for h in horizons}) or set(
        int(h) for h in horizons
    ).issubset(_EXPECTED_HORIZON_PRESETS | {35, 42, 49, 56}), (
        f"presets should be weekly steps; got {horizons!r}"
    )


def test_default_rollout_h_is_member_of_horizons_presets() -> None:
    mod = _import(_ROLLOUT_MOD)
    horizons = getattr(mod, "DEFAULT_ROLLOUT_HORIZONS", None)
    assert horizons is not None, "DEFAULT_ROLLOUT_HORIZONS missing (T-083)"
    h_default = getattr(mod, "DEFAULT_ROLLOUT_H", None)
    assert h_default is not None
    assert int(h_default) % 7 == 0
    assert int(h_default) in {int(h) for h in horizons}, (
        f"DEFAULT_ROLLOUT_H={h_default} must appear in DEFAULT_ROLLOUT_HORIZONS={horizons}"
    )


def test_production_voi_sweep_rollout_h_is_multiple_of_seven() -> None:
    """VOI production default H (non-smoke) must stay weekly-aligned."""
    mod = _import(_VOI_SWEEP_MOD)
    source = _module_source(mod)
    prod_h = getattr(mod, "PRODUCTION_ROLLOUT_H", None)
    if prod_h is None:
        prod_h = getattr(mod, "_PROD_H", None)
    if prod_h is None:
        match = re.search(
            r"_SMOKE_H\s+if\s+use_smoke\s+else\s+(\d+)",
            source,
        )
        if match:
            prod_h = int(match.group(1))
    assert prod_h is not None, (
        "voi.sweep must expose PRODUCTION_ROLLOUT_H / _PROD_H or "
        "(_SMOKE_H if use_smoke else <Hx7>)"
    )
    assert int(prod_h) % 7 == 0, (
        f"production VOI rollout H={prod_h} must be a multiple of 7"
    )
    # Must share the controller preset table (not a one-off magic number).
    rollout = _import(_ROLLOUT_MOD)
    horizons = getattr(rollout, "DEFAULT_ROLLOUT_HORIZONS", None)
    assert horizons is not None, "DEFAULT_ROLLOUT_HORIZONS required for VOI H lock"
    assert int(prod_h) in {int(h) for h in horizons}, (
        f"production VOI H={prod_h} must be in DEFAULT_ROLLOUT_HORIZONS={horizons}"
    )


def test_rollout_module_documents_weekly_horizon_presets() -> None:
    mod = _import(_ROLLOUT_MOD)
    doc = _combined_docs(mod, getattr(mod, "DEFAULT_ROLLOUT_HORIZONS", None))
    source = _module_source(mod).lower()
    blob = doc + "\n" + source
    assert "multiple" in blob or "multiples" in blob or "x7" in blob or "x7" in blob, (
        "rollout module must document Hx7 / multiples-of-7 presets (ADR 0109 #3)"
    )
    assert "7" in blob and ("week" in blob or "periodic" in blob or "mwf" in blob), (
        "rollout docs must tie horizon presets to weekly / MWF periodicity"
    )


# ---------------------------------------------------------------------------
# AC: toy_dp schedule-aware protection / decision epochs
# ---------------------------------------------------------------------------


def test_toy_dp_documents_schedule_aware_certificate() -> None:
    mod = _import(_TOY_MOD)
    doc = _combined_docs(mod, getattr(mod, "solve_toy_dp", None))
    source = _module_source(mod).lower()
    blob = doc + "\n" + source
    assert any(
        token in blob
        for token in (
            "orderschedule",
            "order schedule",
            "order day",
            "order_day",
            "mwf",
            "sun/tue/thu",
            "sun, tue, thu",
        )
    ), (
        "toy_dp must document schedule-aware protection / decision epochs "
        "(no silent daily-order default certificate)"
    )


def test_toy_dp_default_certificate_uses_order_day_epochs() -> None:
    """Default CTL-06 instance must not treat every calendar day as an order epoch."""
    mod = _import(_TOY_MOD)
    # Preferred surfaces: explicit order-day / schedule fields on the module or result.
    order_days = getattr(mod, "ORDER_WEEKDAYS", None)
    if order_days is None:
        order_days = getattr(mod, "DECISION_WEEKDAYS", None)
    if order_days is None:
        order_days = getattr(mod, "ORDER_EPOCH_WEEKDAYS", None)
    schedule = getattr(mod, "DEFAULT_SCHEDULE", None)
    if schedule is None:
        schedule = getattr(mod, "SCHEDULE", None)

    solve = getattr(mod, "solve_toy_dp", None)
    assert callable(solve)
    sig = inspect.signature(solve)
    accepts_schedule = any(
        name in sig.parameters
        for name in ("schedule", "order_schedule", "order_weekdays")
    )

    assert order_days is not None or schedule is not None or accepts_schedule, (
        "toy_dp must expose ORDER_WEEKDAYS / schedule constant or "
        "solve_toy_dp(..., schedule=) for schedule-aware epochs"
    )

    if schedule is not None:
        assert isinstance(schedule, OrderSchedule)
        assert set(schedule.order_weekdays) == set(
            DEFAULT_ORDER_SCHEDULE.order_weekdays
        )

    if order_days is not None:
        days = frozenset(int(d) for d in order_days)
        assert days == frozenset(DEFAULT_ORDER_SCHEDULE.order_weekdays), (
            f"toy DP order epochs {days} must match DEFAULT_ORDER_SCHEDULE "
            f"{set(DEFAULT_ORDER_SCHEDULE.order_weekdays)}"
        )
        # Not the silent daily set {0..6}.
        assert days != frozenset(range(7))


def test_toy_dp_base_policy_protection_is_not_silent_daily_two() -> None:
    """Certificate base arm must not hard-lock daily R+L=2 as the only window."""
    mod = _import(_TOY_MOD)
    source = _module_source(mod)
    # Scalar PROTECTION_DEMAND_DAYS=2 may remain as legacy, but the default
    # certificate path must consult schedule / day-indexed coverage.
    tree = ast.parse(source)
    has_schedule_use = any(
        isinstance(node, ast.Name)
        and node.id
        in {
            "OrderSchedule",
            "DEFAULT_ORDER_SCHEDULE",
            "ORDER_WEEKDAYS",
            "DECISION_WEEKDAYS",
            "protection_days",
        }
        for node in ast.walk(tree)
    )
    solve = mod.solve_toy_dp
    sig = inspect.signature(solve)
    has_schedule_param = any(
        p in sig.parameters for p in ("schedule", "order_schedule", "order_weekdays")
    )
    assert has_schedule_use or has_schedule_param, (
        "toy_dp default certificate still looks daily-only; wire OrderSchedule "
        "or day-indexed protection epochs (T-083)"
    )


# ---------------------------------------------------------------------------
# AC: M2 gates / ladder under default OrderSchedule + day-indexed Rung0
# ---------------------------------------------------------------------------


def test_m2_gates_module_wires_default_order_schedule() -> None:
    mod = _import(_GATES_MOD)
    source = _module_source(mod)
    assert "OrderSchedule" in source or "DEFAULT_ORDER_SCHEDULE" in source, (
        "m2_gates must import / use DEFAULT_ORDER_SCHEDULE (orders Sun/Tue/Thu)"
    )


def test_m2_gates_beta1_consumes_day_indexed_rung0_weights() -> None:
    """Age-blind gate arm must use T-081 day-indexed survival weights + schedule."""
    mod = _import(_GATES_MOD)
    gate = getattr(mod, "assert_beta1_degeneracy", None)
    assert callable(gate)
    try:
        body = inspect.getsource(gate)
    except OSError:
        body = _module_source(mod)
    assert "CorrectedAgeBlindPolicy" in body
    uses_schedule_kw = "schedule=" in body or "schedule =" in body
    uses_day_index = any(
        token in body
        for token in (
            "mean_survival_weight_for_day",
            "survival_weights_by_weekday",
            "periodic_survival",
            "weights_by_weekday",
            "DEFAULT_ORDER_SCHEDULE",
            "OrderSchedule",
        )
    )
    assert uses_schedule_kw or uses_day_index, (
        "assert_beta1_degeneracy must attach OrderSchedule and/or day-indexed "
        "Rung 0 survival weights (T-081 / T-083)"
    )


def test_m2_gates_beta1_exercises_order_days_under_schedule() -> None:
    """Gate must compare policies on Sun/Tue/Thu (not only legacy daily day=0)."""
    mod = _import(_GATES_MOD)
    source = _module_source(mod)
    # Look for order-day indices (6,1,3) or weekday names / can_order usage.
    mentions_order_days = any(
        token in source.lower()
        for token in (
            "order_day",
            "order days",
            "sun",
            "tue",
            "thu",
            "can_order",
            "weekday",
        )
    )
    # Or explicit day loop over schedule order weekdays.
    mentions_days = "day=" in source and (
        "for day" in source.lower() or "order_weekdays" in source
    )
    assert mentions_order_days or mentions_days, (
        "beta1 gate must exercise default OrderSchedule order days "
        f"(Sun/Tue/Thu={sorted(DEFAULT_ORDER_SCHEDULE.order_weekdays)})"
    )


def test_assert_beta1_degeneracy_passes_under_default_schedule() -> None:
    """After retune, ENG-04 beta1 gate remains green under MWF OrderSchedule."""
    mod = _import(_GATES_MOD)
    gate = getattr(mod, "assert_beta1_degeneracy", None)
    assert callable(gate)
    # Precondition: module must already wire schedule (else this is not the retune).
    source = _module_source(mod)
    if "DEFAULT_ORDER_SCHEDULE" not in source and "OrderSchedule" not in source:
        pytest.fail(
            "m2_gates has not been updated for OrderSchedule yet - "
            "wire schedule before retuning thresholds (T-083)"
        )
    result = gate()
    ok = bool(getattr(result, "ok", result))
    assert ok, (
        f"assert_beta1_degeneracy must pass under default OrderSchedule; got {result!r}. "
        "Implementer may retune matched demand fractiles / day-indexed weights "
        "and record new thresholds in m2_gates."
    )


def test_m2_ladder_or_alpha_tune_attaches_order_schedule() -> None:
    """Ladder profit arms must run under default OrderSchedule (episode gate)."""
    ladder = _import(_LADDER_MOD)
    alpha = _import(_ALPHA_MOD)
    blob = _module_source(ladder) + "\n" + _module_source(alpha)
    assert "DEFAULT_ORDER_SCHEDULE" in blob or "OrderSchedule" in blob, (
        "m2_ladder / alpha_tune must attach DEFAULT_ORDER_SCHEDULE so gates "
        "run with orders only on Sun/Tue/Thu"
    )
    # Adapter / policy construction should pass schedule into SW / Rung0.
    assert "schedule=" in blob or "schedule =" in blob, (
        "ladder / alpha_tune policy adapters must pass schedule= into controllers"
    )


def test_assert_dp_certificate_uses_schedule_aware_toy_dp() -> None:
    mod = _import(_GATES_MOD)
    source = _module_source(mod)
    # DP gate calls solve_toy_dp; after T-083 that certificate is schedule-aware.
    assert "solve_toy_dp" in source
    toy = _import(_TOY_MOD)
    toy_src = _module_source(toy).lower()
    assert any(
        t in toy_src
        for t in ("orderschedule", "order_weekday", "order day", "mwf", "schedule")
    ), "DP certificate gate inherits schedule-aware toy_dp (T-083)"


# ---------------------------------------------------------------------------
# AC: burn-in acknowledges periodic age under MWF
# ---------------------------------------------------------------------------


def test_burn_in_docs_acknowledge_periodic_age_under_mwf() -> None:
    """Episode / burn-in surfaces must not claim daily stationary age only."""
    candidates = (
        _EPISODE_MOD,
        "blueberries_voi.sim",
        _VOI_SWEEP_MOD,
        "blueberries_voi.sim.m2_ladder",
    )
    blobs: list[str] = []
    for name in candidates:
        try:
            mod = _import(name)
        except ImportError:
            continue
        blobs.append(_combined_docs(mod))
        try:
            blobs.append(_module_source(mod).lower())
        except AssertionError:
            continue
    text = "\n".join(blobs)
    assert "periodic" in text, (
        "burn-in / episode docs must acknowledge periodic age under MWF "
        "(ADR 0109), not only daily stationary burn-in"
    )
    assert any(
        token in text for token in ("mwf", "order schedule", "orderschedule", "weekly")
    ), "periodic burn-in note must reference MWF / OrderSchedule / weekly cadence"


def test_production_burn_in_default_is_multiple_of_seven() -> None:
    """Production burn-in length should cover whole weeks under periodic age."""
    sweep = _import(_VOI_SWEEP_MOD)
    n_burn = getattr(sweep, "PRODUCTION_N_BURN", None)
    if n_burn is None:
        n_burn = getattr(sweep, "_PROD_N_BURN", None)
    assert n_burn is not None, (
        "voi.sweep must expose PRODUCTION_N_BURN / _PROD_N_BURN for T-083 lock"
    )
    assert int(n_burn) > 0
    assert int(n_burn) % 7 == 0, (
        f"production n_burn={n_burn} must be a multiple of 7 under periodic MWF age "
        "(daily-stationary 30-day default is superseded)"
    )


def test_episode_default_n_burn_documents_or_uses_weekly_alignment() -> None:
    """Closed-loop default burn-in is weekly-aligned or explicitly documented."""
    mod = _import(_EPISODE_MOD)
    fn = mod.run_closed_loop_episode
    sig = inspect.signature(fn)
    assert "n_burn" in sig.parameters
    default = sig.parameters["n_burn"].default
    assert default is not inspect.Parameter.empty
    doc = _combined_docs(mod, fn) + "\n" + _module_source(mod).lower()
    if int(default) % 7 == 0:
        return
    assert "periodic" in doc and ("burn" in doc or "n_burn" in doc), (
        f"run_closed_loop_episode n_burn default={default} is not x7; "
        "module must document periodic-age burn-in under MWF if kept"
    )
