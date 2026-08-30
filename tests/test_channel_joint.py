"""Tests for closed-loop channel-joint shards (nb19)."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.experiments.channel_joint import (
    all_obs_channels_product,
    channel_joint_job_grid,
    merge_channel_joint_rows,
    run_seed_channel_joint,
)
from blueberries_voi.experiments.voi_profit import (
    _damped_sw_act_kw,
    profit_session_config,
)
from blueberries_voi.filter.types import ObsChannels, channels_for_preset
from blueberries_voi.simulator import EngineSession
from blueberries_voi.simulator.schema import validate_day_delta

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


@_RUST
def test_gsin_high_rho_no_filter_collapse_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic repro from 2026-08-30 GSIN PF collapse (plan §4).

    Before the §2 fix, this (seed, channel, alpha, rho) combination froze the
    unit particle filter's belief bit-for-bit for the rest of the episode
    while the real shelf sold down toward zero, and the controller — reading
    a frozen belief that still claimed the old on-hand count — stopped
    reordering. `infeasible == filter_n` (total per-particle likelihood
    failure) is *not* itself the bug: GSIN's cross-lot allocation
    approximation genuinely fails on some days and recovers on its own, which
    is expected and asserted separately. The actual defect signature is the
    belief staying frozen across a day with real depletion.

    Under the narrow collapse fix (ADR / plan §4 option a), total-collapse
    rescue days may still leave ``sum(lot_counts)`` transiently above truth
    on-hand when per-lot sales removal cannot fully align particle segmentation
    with observed GSIN sales — that gap is not the freeze bug and is not
    asserted here.
    """
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    seed = 1784690067
    alpha = 0.7437600021964654
    rho = 1.5938240528614713
    n_burn = 7
    n_score = 45
    filter_n = 24
    channels = ObsChannels(
        code_type="gsin",
        scan_waste=True,
        delivery_history="none",
    )
    session = EngineSession()
    cfg = profit_session_config(filter_n=filter_n)
    session.init(cfg, seed=seed)
    session.set_obs_channels(channels)
    act_kw = _damped_sw_act_kw(alpha, rho)
    for _ in range(n_burn):
        delta = session.act(**act_kw)
        validate_day_delta(delta)

    prev_lot_counts: list[float] | None = None
    for _ in range(n_score):
        delta = session.act(**act_kw)
        validate_day_delta(delta)
        fh = delta.get("filter_health")
        assert isinstance(fh, Mapping), "filter must run on scored days"

        belief = delta["belief"]
        lot_counts = list(belief["lot_counts"])
        day = delta["day"]
        depleted = (int(day["sales_total"]) + int(day["waste_total"])) > 0

        assert not (depleted and lot_counts == prev_lot_counts), (
            f"belief frozen across a day with real depletion: lot_counts={lot_counts}"
        )
        prev_lot_counts = lot_counts

    row = run_seed_channel_joint(
        seed,
        channels,
        n_burn=n_burn,
        n_score=n_score,
        filter_n=filter_n,
        controller_alpha=alpha,
        controller_rho=rho,
    )
    assert row["filter_collapse_days"] == 0
