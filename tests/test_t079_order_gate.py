"""T-079: episode / session OrderSchedule gate (CAL-A2) — RED before implement.

Locks ``.team/specs/T-079.md``, ADR 0111 (schedule), ADR 0113 (``day=`` shim):

* Closed-loop / day_driver / EngineSession force ``order_qty=0`` on non-order days
* Policy / scripted qty passes through on Sun/Tue/Thu (subject to case rounding)
* Daily ``day_step`` continues (contiguous days + demand every day)
* Open-loop / scripted sequences **coerce** nonzero orders on non-order days to 0
  (chosen over reject — matches closed-loop physics gate; ``step_n`` stays usable)
* ``draw_demand`` / ``day_step`` ``day=`` forwarded when supported; absent → prior μ
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np
import pytest

from blueberries_voi.controller.ordering import case_round
from blueberries_voi.model import ModelParams, draw_demand
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.rng import STREAM_DEMAND, spawn_rng
from blueberries_voi.sim.episode import run_closed_loop_episode
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE, OrderSchedule
from blueberries_voi.simulator.day_driver import DayDriverState, advance_day
from blueberries_voi.simulator.session import EngineSession

_EPOCH = date(2024, 1, 1)
_ORDER_WEEKDAYS = frozenset({6, 1, 3})  # Sun / Tue / Thu


def _weekday(day: int) -> int:
    return (_EPOCH + timedelta(days=day)).weekday()


def _is_order_day(day: int, schedule: OrderSchedule = DEFAULT_ORDER_SCHEDULE) -> bool:
    return bool(schedule.can_order(day))


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T079-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _minimal_session_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": 16,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": False,
    }
    cfg.update(overrides)
    return cfg


class _ConstantOrderPolicy:
    """Always returns a fixed raw order qty (pre case_round / gate)."""

    def __init__(self, q: int) -> None:
        self.q = int(q)
        self.calls: list[int] = []

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
        **_kwargs: Any,
    ) -> int:
        del belief, pending_orders
        self.calls.append(int(day))
        return max(0, self.q)


def _day_delta_order_qty(delta: Mapping[str, Any]) -> int:
    day_obj = delta.get("day")
    assert isinstance(day_obj, Mapping), "DayDelta.day must be a mapping"
    assert "order_qty" in day_obj, "DayDelta.day must include order_qty"
    return int(day_obj["order_qty"])


# ---------------------------------------------------------------------------
# AC: closed-loop forces order_qty=0 on non-order days
# ---------------------------------------------------------------------------


def test_closed_loop_forces_zero_order_on_non_order_days() -> None:
    """Policy may ask nonzero every day; physics applies 0 off Sun/Tue/Thu."""
    raw = 16
    policy = _ConstantOrderPolicy(raw)
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=0,
        n_score=14,
        root_seed=11,
        run_id="t079-gate-zero",
    )
    assert len(ep.days) == 14
    non_order = [d for d in ep.days if not _is_order_day(d.day)]
    assert non_order, "fixture horizon must include non-order weekdays"
    for d in non_order:
        assert d.order_qty == 0, (
            f"day={d.day} weekday={_weekday(d.day)} must force order_qty=0 "
            f"(got {d.order_qty}; policy asked {raw})"
        )


def test_closed_loop_runner_accepts_schedule_kwarg() -> None:
    """Interfaces: ``run_closed_loop_episode(..., schedule=)`` (default schedule OK)."""
    sig = inspect.signature(run_closed_loop_episode)
    assert "schedule" in sig.parameters, (
        "run_closed_loop_episode must accept schedule: OrderSchedule | None "
        "per .team/specs/T-079.md Interfaces"
    )
    custom = OrderSchedule(order_weekdays=frozenset({0}))  # Monday-only
    policy = _ConstantOrderPolicy(8)
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=0,
        n_score=7,
        root_seed=3,
        run_id="t079-custom-sched",
        schedule=custom,
    )
    for d in ep.days:
        if _weekday(d.day) == 0:
            assert d.order_qty == 8
        else:
            assert d.order_qty == 0


# ---------------------------------------------------------------------------
# AC: on order days policy qty passes through (Sun/Tue/Thu nonzero)
# ---------------------------------------------------------------------------


def test_closed_loop_passes_policy_qty_on_order_days() -> None:
    raw = 16
    expected = int(case_round(float(raw), 8))
    assert expected > 0
    policy = _ConstantOrderPolicy(raw)
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=0,
        n_score=14,
        root_seed=22,
        run_id="t079-pass-through",
    )
    order_days = [d for d in ep.days if _is_order_day(d.day)]
    assert order_days, "expected Sun/Tue/Thu in horizon"
    labels = {_weekday(d.day) for d in order_days}
    assert labels & {6, 1, 3}, "order days must include Sun/Tue/Thu weekdays"
    nonzero = [d for d in order_days if d.order_qty > 0]
    assert nonzero, (
        "at least one Sun/Tue/Thu day must receive nonzero order when policy asks"
    )
    for d in order_days:
        assert d.order_qty == expected, (
            f"order day={d.day} weekday={_weekday(d.day)}: "
            f"expected policy qty {expected}, got {d.order_qty}"
        )


# ---------------------------------------------------------------------------
# AC: day_step every calendar day (contiguous indices + demand)
# ---------------------------------------------------------------------------


def test_closed_loop_runs_day_step_every_calendar_day_with_demand() -> None:
    policy = _ConstantOrderPolicy(8)
    n_score = 10
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=0,
        n_score=n_score,
        root_seed=42,
        run_id="t079-daily-physics",
    )
    days = [d.day for d in ep.days]
    assert days == list(range(n_score)), (
        f"day indices must be contiguous 0..{n_score - 1}; got {days}"
    )
    for d in ep.days:
        assert isinstance(d.demand, int), f"day={d.day} demand must be int"
        assert d.demand >= 0, f"day={d.day} demand must be drawn (got {d.demand})"
    # Non-order weekdays must still appear in the log (physics tick, not weekly jump).
    non_order_days = [d.day for d in ep.days if not _is_order_day(d.day)]
    assert non_order_days, "horizon must include non-order calendar days"
    for day_idx in non_order_days:
        row = ep.days[day_idx]
        assert row.demand >= 0
        assert row.day == day_idx


# ---------------------------------------------------------------------------
# AC: day_driver / EngineSession honor the same gate
# ---------------------------------------------------------------------------


def test_advance_day_forces_zero_order_on_non_order_day() -> None:
    params = ModelParams(case_size=8)
    state = DayDriverState(
        cohorts=[],
        pending={},
        next_lot_id=1,
        episode_day=0,  # Monday — non-order
        rbpf=None,
    )
    assert not _is_order_day(0)
    result = advance_day(
        state,
        16,
        shipments=_fixture_shipments(),
        params=params,
        root_seed=7,
        run_id="t079-adv-mon",
        enable_filter=False,
    )
    assert int(result.day["order_qty"]) == 0, (
        "advance_day must gate order_qty to 0 on non-order days"
    )


def test_advance_day_passes_order_on_order_day() -> None:
    params = ModelParams(case_size=8)
    state = DayDriverState(
        cohorts=[],
        pending={},
        next_lot_id=1,
        episode_day=1,  # Tuesday — order day
        rbpf=None,
    )
    assert _is_order_day(1)
    result = advance_day(
        state,
        16,
        shipments=_fixture_shipments(),
        params=params,
        root_seed=7,
        run_id="t079-adv-tue",
        enable_filter=False,
    )
    # day_driver uses ceil-to-case; 16 already on a case boundary.
    assert int(result.day["order_qty"]) == 16


def test_engine_session_step_forces_zero_on_non_order_day() -> None:
    session = EngineSession()
    session.init(_minimal_session_config(), seed=5)
    assert session._state.episode_day == 0  # Monday
    delta = session.step(16)
    assert _day_delta_order_qty(delta) == 0
    # Tuesday: same requested qty must pass through.
    delta_tue = session.step(16)
    assert _day_delta_order_qty(delta_tue) == 16


def test_engine_session_step_n_gates_mixed_scripted_orders() -> None:
    """Scripted sequence: coerce nonzero → 0 on non-order days (locked choice)."""
    session = EngineSession()
    session.init(_minimal_session_config(), seed=9)
    # Days 0..6: Mon..Sun — nonzero asked every day.
    orders = [16, 16, 16, 16, 16, 16, 16]
    deltas = session.step_n(orders)
    assert len(deltas) == 7
    for i, delta in enumerate(deltas):
        qty = _day_delta_order_qty(delta)
        if _is_order_day(i):
            assert qty == 16, f"order day {i}: expected 16, got {qty}"
        else:
            assert qty == 0, f"non-order day {i}: expected coerced 0, got {qty}"


# ---------------------------------------------------------------------------
# AC: open-loop coerces nonzero on non-order days (documented choice)
# ---------------------------------------------------------------------------


def test_open_loop_coerces_orders_to_zero_on_non_order_days() -> None:
    """Open-loop locks **coerce-to-0** (not reject) on non-order days.

    Rejecting would abort mid-episode when base-stock asks for stock; coerce
    matches the closed-loop / session physics gate.
    """
    from blueberries_voi.sim import run_episode

    ep = run_episode(
        params=ModelParams(case_size=8),
        shipments=_fixture_shipments(),
        root_seed=13,
        run_id="t079-ol-coerce",
        n_burn=0,
        n_score=14,
        S=60,
        lead_time=1,
    )
    assert len(ep.days) == 14
    for d in ep.days:
        if not _is_order_day(d.day):
            assert d.order_qty == 0, (
                f"open-loop day={d.day} weekday={_weekday(d.day)} must coerce "
                f"order_qty to 0 (got {d.order_qty})"
            )


def test_open_loop_may_order_on_sun_tue_thu() -> None:
    from blueberries_voi.sim import run_episode

    ep = run_episode(
        params=ModelParams(case_size=8),
        shipments=_fixture_shipments(),
        root_seed=13,
        run_id="t079-ol-order-days",
        n_burn=0,
        n_score=14,
        S=60,
        lead_time=1,
    )
    order_days = [d for d in ep.days if _is_order_day(d.day)]
    assert any(d.order_qty > 0 for d in order_days), (
        "open-loop should still place stock on at least one order day under S=60"
    )


# ---------------------------------------------------------------------------
# AC: draw_demand / day_step day= compatibility shim (ADR 0113)
# ---------------------------------------------------------------------------


def test_draw_demand_without_day_keeps_prior_mu() -> None:
    """Absent / unused ``day`` keeps pre-CAL i.i.d. μ behaviour."""
    params = ModelParams(demand_mu=30.0, demand_vm=2.0)
    rng = spawn_rng(99, run_id="t079-mu", day=1, stream=STREAM_DEMAND)
    sample = draw_demand(rng, params)
    assert isinstance(sample, int)
    assert sample >= 0
    sig = inspect.signature(draw_demand)
    if "day" in sig.parameters:
        rng2 = spawn_rng(99, run_id="t079-mu", day=1, stream=STREAM_DEMAND)
        assert draw_demand(rng2, params, day=None) == sample  # type: ignore[call-arg]


def test_closed_loop_forwards_day_kw_to_day_step_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``day_step`` accepts ``day=``, episode must pass the episode day.

    Pre-T-082 production ``day_step`` may lack the kwarg; the test installs a
    compatible wrapper so the ADR 0113 shim obligation is observable now.
    """
    import blueberries_voi.sim.episode as episode_mod
    from blueberries_voi.model import day_step as real_day_step

    recorded: list[int | None] = []

    def day_step_with_day(
        cohorts: Sequence[Any],
        *,
        day: int | None = None,
        **kwargs: Any,
    ) -> Any:
        recorded.append(day)
        return real_day_step(cohorts, **kwargs)

    monkeypatch.setattr(episode_mod, "day_step", day_step_with_day)

    n_score = 7
    run_closed_loop_episode(
        _ConstantOrderPolicy(0),
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=0,
        n_score=n_score,
        root_seed=1,
        run_id="t079-day-fwd",
    )
    assert recorded == list(range(n_score)), (
        "closed-loop must pass day=0..{0} into day_step when supported; got {1}".format(
            n_score - 1, recorded
        )
    )


def test_advance_day_forwards_day_kw_to_day_step_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.simulator.day_driver as driver_mod
    from blueberries_voi.model import day_step as real_day_step

    recorded: list[int | None] = []

    def day_step_with_day(
        cohorts: Sequence[Any],
        *,
        day: int | None = None,
        **kwargs: Any,
    ) -> Any:
        recorded.append(day)
        return real_day_step(cohorts, **kwargs)

    monkeypatch.setattr(driver_mod, "day_step", day_step_with_day)

    state = DayDriverState(
        cohorts=[],
        pending={},
        next_lot_id=1,
        episode_day=3,
        rbpf=None,
    )
    advance_day(
        state,
        0,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        root_seed=2,
        run_id="t079-adv-day-fwd",
        enable_filter=False,
    )
    assert recorded == [3], f"advance_day must forward day=3; got {recorded}"
