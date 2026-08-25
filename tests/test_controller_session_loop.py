"""Controller session loop (Option A) — T-controller-notebook."""

from __future__ import annotations

from typing import Any

import pytest

from blueberries_voi.controller.session_loop import (
    ControllerContext,
    ControllerStepLog,
    EpisodeTotals,
    context_from_snapshot,
    default_session_config,
    episode_totals_from_logs,
    pipeline_wire_to_pending,
    run_act_episode,
    run_controller_episode,
    run_controller_session,
)
from blueberries_voi.controller.starter import (
    NaiveBaseStockController,
    TabularQLearningController,
    discretize_on_hand,
    weekday_index,
)
from blueberries_voi.filter.belief import ShelfBelief, unflatten_shelf_belief
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.simulator import EngineSession
from blueberries_voi.simulator.belief import shelf_belief_from_flat

pytestmark_rust = pytest.mark.skipif(
    __import__("blueberries_voi.backend", fromlist=["rust_available"]).rust_available()
    is False,
    reason="requires blueberries_voi._core",
)


def _flat_belief() -> dict[str, Any]:
    return {
        "lot_counts": [12.0, 4.0],
        "f_marginals": [0.0, 0.25, 0.5, 0.25] * 2,
        "f_grid": [0.0, 0.5, 1.0],
        "L": 2,
        "K": 3,
    }


def test_pipeline_wire_to_pending_skips_zero_qty() -> None:
    wire = [
        {"arrival_day": 3, "qty": 16},
        {"arrival_day": 5, "qty": 0},
        {"arrival_day": 7, "qty": 8},
    ]
    assert pipeline_wire_to_pending(wire) == {3: 16, 7: 8}


def test_context_from_snapshot_builds_schedule_and_gates() -> None:
    snap = {
        "seq": 2,
        "episode_day": 1,
        "belief": _flat_belief(),
        "pipeline": [{"arrival_day": 4, "qty": 8}],
        "schedule": {
            "delivery_weekdays": [0, 2, 4],
            "order_weekdays": [6, 1, 3],
            "lead_time_days": 1,
            "epoch": "2024-01-01",
        },
        "live_lots": [{"lot_id": 0, "n": 16, "mean_f": 0.9}],
    }
    ctx = context_from_snapshot(snap)
    assert ctx.seq == 2
    assert ctx.episode_day == 1
    assert ctx.pending_orders == {4: 8}
    assert ctx.on_hand == 16
    assert isinstance(ctx.belief, ShelfBelief)
    assert ctx.schedule.order_weekdays == DEFAULT_ORDER_SCHEDULE.order_weekdays
    assert ctx.can_order == ctx.schedule.can_order(1)


def test_controller_step_log_day_profit() -> None:
    delta = {
        "seq": 1,
        "episode_day": 0,
        "day": {
            "day": 0,
            "order_qty": 8,
            "sales_total": 10,
            "waste_total": 2,
            "demand": 12,
            "arrivals": 0,
            "L": 20,
        },
    }
    log = ControllerStepLog.from_delta(delta)
    assert log.day_profit == 2.0 * 10 - 1.5 * 2 - 3.0 * 2


def test_default_session_config_smoke_shipments() -> None:
    cfg = default_session_config()
    smoke = smoke_cool_shipments()
    assert len(cfg["shipments"]) == len(smoke)
    assert cfg["shipments"][0].shipment_id == smoke[0].shipment_id
    assert cfg["n_particles"] == 200
    assert cfg["lead_time"] == 1
    assert cfg["belief_source"] == "filter"
    assert cfg["delivery_weekdays"] == [0, 2, 4]


def test_starter_helpers() -> None:
    assert weekday_index(0) == 0
    assert weekday_index(8) == 1
    assert discretize_on_hand(0, max_on_hand=80, n_bins=10) == 0
    assert discretize_on_hand(80, max_on_hand=80, n_bins=10) == 9


def test_naive_base_stock_zero_on_non_order_day() -> None:
    belief = unflatten_shelf_belief(_flat_belief())
    ctx = ControllerContext(
        episode_day=2,
        seq=0,
        belief=belief,
        pending_orders={},
        schedule=DEFAULT_ORDER_SCHEDULE,
        can_order=False,
        on_hand=10,
    )
    ctrl = NaiveBaseStockController(target_units=48, case_size=8)
    assert ctrl.order(ctx) == 0


def test_tabular_q_learning_no_order_when_gated() -> None:
    belief = unflatten_shelf_belief(_flat_belief())
    ctx = ControllerContext(
        episode_day=0,
        seq=0,
        belief=belief,
        pending_orders={},
        schedule=DEFAULT_ORDER_SCHEDULE,
        can_order=False,
        on_hand=5,
    )
    ctrl = TabularQLearningController([0, 8, 16], epsilon=0.0, seed=1)
    assert ctrl.order(ctx) == 0


def test_tabular_q_learning_observe_updates_q() -> None:
    belief = shelf_belief_from_flat(_flat_belief())
    ctx = ControllerContext(
        episode_day=1,
        seq=1,
        belief=belief,
        pending_orders={},
        schedule=DEFAULT_ORDER_SCHEDULE,
        can_order=True,
        on_hand=20,
    )
    ctrl = TabularQLearningController([8, 16], epsilon=0.0, seed=0)
    qty = ctrl.order(ctx)
    assert qty in (8, 16)
    log = ControllerStepLog(
        episode_day=1,
        seq=1,
        order_qty=qty,
        sales_total=10,
        waste_total=1,
        demand=10,
        arrivals=0,
        on_hand=18,
        day_profit=17.5,
    )
    ctrl.observe(ctx, log)
    state = (weekday_index(1), discretize_on_hand(20))
    assert ctrl._q[state][qty] > 0.0


class _ConstantController:
    def __init__(self, qty: int) -> None:
        self.qty = int(qty)

    def order(self, ctx: ControllerContext) -> int:
        return self.qty if ctx.can_order else 0


@pytestmark_rust
def test_engine_session_snapshot_after_init(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    session = EngineSession()
    session.init(default_session_config(n_particles=32, H=3), seed=7)
    snap = session.snapshot()
    assert "belief" in snap
    assert "schedule" in snap
    ctx = context_from_snapshot(snap)
    assert ctx.episode_day == 0


@pytestmark_rust
def test_run_controller_session_constant_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    session = EngineSession()
    cfg = default_session_config(n_particles=32, H=3, n_rollout_paths=1)
    session.init(cfg, seed=11)
    logs = run_controller_session(session, _ConstantController(8), n_days=5)
    assert len(logs) == 5
    assert all(log.order_qty in (0, 8) for log in logs)


@pytestmark_rust
def test_schedule_gate_zeros_orders_on_non_order_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    session = EngineSession()
    session.init(
        default_session_config(n_particles=32, H=3, n_rollout_paths=1),
        seed=21,
    )
    logs = run_controller_session(session, _ConstantController(16), n_days=14)
    for log in logs:
        day = log.episode_day
        if not DEFAULT_ORDER_SCHEDULE.can_order(day):
            assert log.order_qty == 0


def test_episode_totals_from_logs_sums_profit_waste_stockout() -> None:
    logs = [
        ControllerStepLog(
            episode_day=0,
            seq=1,
            order_qty=8,
            sales_total=10,
            waste_total=2,
            demand=12,
            arrivals=0,
            on_hand=20,
            day_profit=17.0,
        ),
        ControllerStepLog(
            episode_day=1,
            seq=2,
            order_qty=0,
            sales_total=8,
            waste_total=1,
            demand=8,
            arrivals=0,
            on_hand=18,
            day_profit=14.5,
        ),
        ControllerStepLog(
            episode_day=2,
            seq=3,
            order_qty=0,
            sales_total=5,
            waste_total=0,
            demand=7,
            arrivals=0,
            on_hand=13,
            day_profit=4.0,
        ),
    ]
    totals = episode_totals_from_logs(
        logs,
        seed=99,
        policy_label="fixture",
    )
    assert totals == EpisodeTotals(
        profit=35.5,
        waste=3,
        stockout=4,
        seed=99,
        policy_label="fixture",
    )


@pytestmark_rust
def test_run_act_episode_damped_sw_one_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    cfg = default_session_config(n_particles=32, H=3, n_rollout_paths=0)
    totals = run_act_episode(
        cfg,
        seed=17,
        n_days=7,
        policy="damped_sw",
        alpha=0.9,
        rho=0.8,
        policy_label="damped_sw",
    )
    assert totals.seed == 17
    assert totals.policy_label == "damped_sw"
    assert totals.waste >= 0
    assert totals.stockout >= 0


@pytestmark_rust
def test_run_act_episode_paired_seed_reproducible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    cfg = default_session_config(n_particles=32, H=3, n_rollout_paths=0)
    first = run_act_episode(
        cfg,
        seed=42,
        n_days=5,
        policy="damped_sw",
        policy_label="damped_sw",
    )
    second = run_act_episode(
        cfg,
        seed=42,
        n_days=5,
        policy="damped_sw",
        policy_label="damped_sw",
    )
    assert first == second


@pytestmark_rust
def test_run_controller_episode_naive_base_stock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    cfg = default_session_config(n_particles=32, H=3, n_rollout_paths=0)
    ctrl = NaiveBaseStockController(target_units=48, case_size=8)
    totals = run_controller_episode(
        cfg,
        ctrl,
        seed=23,
        n_days=7,
        policy_label="naive",
    )
    assert totals.seed == 23
    assert totals.policy_label == "naive"
    assert totals.waste >= 0
    assert totals.stockout >= 0


@pytestmark_rust
def test_paired_seed_benchmark_naive_and_damped_sw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same seed + config → comparable EpisodeTotals across Option A and act()."""
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    cfg = default_session_config(n_particles=32, H=3, n_rollout_paths=0)
    seed = 31
    n_days = 7
    naive = run_controller_episode(
        cfg,
        NaiveBaseStockController(target_units=48, case_size=8),
        seed,
        n_days,
        policy_label="naive",
    )
    damped = run_act_episode(
        cfg,
        seed,
        n_days,
        policy="damped_sw",
        policy_label="damped_sw",
    )
    assert naive.seed == damped.seed == seed
    assert naive.policy_label == "naive"
    assert damped.policy_label == "damped_sw"
