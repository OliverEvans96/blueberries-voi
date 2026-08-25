"""Tests for nb19 Modal budget planning."""

from __future__ import annotations

import pytest

from blueberries_voi.experiments.batch_budget import (
    BUDGET_SAFETY,
    CPU_HR_LIMIT,
    WALL_LIMIT_S,
    assert_within_budget,
    plan_channel_joint_budget,
)


def test_plan_channel_joint_budget_respects_caps() -> None:
    plan = plan_channel_joint_budget(30.0, max_seeds=6)
    assert_within_budget(plan)
    assert plan.n_channels == 12
    assert plan.shard_count == plan.n_seeds * 12
    assert plan.est_wall_s <= WALL_LIMIT_S * BUDGET_SAFETY
    assert plan.est_cpu_hr <= CPU_HR_LIMIT * BUDGET_SAFETY


def test_plan_prefers_more_seeds_before_longer_score() -> None:
    fast = plan_channel_joint_budget(15.0, max_seeds=8, n_score_min=10, n_score_max=14)
    assert fast.n_seeds >= 6


def test_assert_within_budget_raises_when_exceeded() -> None:
    plan = plan_channel_joint_budget(30.0, max_seeds=1)
    bad = type(plan)(
        n_seeds=plan.n_seeds,
        n_score=plan.n_score,
        n_burn=plan.n_burn,
        n_channels=plan.n_channels,
        shard_count=plan.shard_count,
        t_shard_s=plan.t_shard_s,
        est_wall_s=WALL_LIMIT_S * 2,
        est_cpu_hr=plan.est_cpu_hr,
    )
    with pytest.raises(RuntimeError, match="wall"):
        assert_within_budget(bad)


def test_plan_raises_when_no_feasible_grid() -> None:
    with pytest.raises(RuntimeError, match="no feasible"):
        plan_channel_joint_budget(600.0, max_seeds=1)
