"""Tests for closed-loop channel-joint shards (nb19)."""

from __future__ import annotations

import json

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.experiments.channel_joint import (
    all_obs_channels_product,
    channel_joint_job_grid,
    merge_channel_joint_rows,
    run_seed_channel_joint,
)
from blueberries_voi.filter.types import channels_for_preset

_RUST = pytest.mark.skipif(
    _maybe_core is None,
    reason="blueberries_voi._core not built",
)


def test_all_obs_channels_product_count_and_axes() -> None:
    combos = all_obs_channels_product()
    assert len(combos) == 12
    code_types = {c.code_type for c in combos}
    assert code_types == {"upc", "gsin"}
    deliveries = {c.delivery_history for c in combos}
    assert deliveries == {"none", "pack_date", "temperature_history"}


def test_channel_joint_job_grid_size() -> None:
    seeds = (42, 7)
    grid = channel_joint_job_grid(seeds)
    assert len(grid) == 2 * 12


def test_merge_channel_joint_rows_dedup() -> None:
    shard = {
        "seed": 42,
        "key": "code=upc|waste=0|hist=none",
        "profit": 1.0,
        "waste_total": 0,
        "stockout": 0,
        "mae_f": 0.1,
        "mae_dist": 0.2,
        "code_type": "upc",
        "waste": "off",
        "delivery": "none",
        "preset": "P0",
    }
    rows = merge_channel_joint_rows([shard, dict(shard)])
    assert len(rows) == 1


@_RUST
def test_run_seed_channel_joint_tiny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    ch = channels_for_preset("P0")
    out = run_seed_channel_joint(42, ch, n_burn=1, n_score=2)
    assert out["seed"] == 42
    assert out["preset"] == "P0"
    assert "mae_f" in out
    assert "mae_dist" in out
    assert "profit" in out
    assert out["n_live_days"] >= 1
    json.dumps(out)
