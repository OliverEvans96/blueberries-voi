"""Session-aligned profit oracle (belief_source=truth on EngineSession)."""

from __future__ import annotations

import os

import pytest

from blueberries_voi.experiments.voi_profit import (
    DEFAULT_N_BURN,
    DEFAULT_N_SCORE,
    run_seed_channel_profit,
    run_seed_oracle_profit,
)
from blueberries_voi.filter.types import channels_for_preset

_RUST = pytest.mark.skipif(
    os.environ.get("BLUEBERRIES_VOI_BACKEND") != "rust",
    reason="requires BLUEBERRIES_VOI_BACKEND=rust and built _core",
)


@_RUST
def test_oracle_profit_reports_real_waste_and_stockout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    row = run_seed_oracle_profit(
        42,
        n_burn=DEFAULT_N_BURN,
        n_score=DEFAULT_N_SCORE,
    )
    assert row["oracle"] is True
    assert row["key"] == "B-state"
    assert row["waste"] > 0 or row["stockout"] > 0
    assert not (row["waste"] == 0 and row["stockout"] == 0)


@_RUST
def test_oracle_profit_differs_from_p0_on_belief_driven_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    seed = 42
    oracle = run_seed_oracle_profit(
        seed,
        n_burn=DEFAULT_N_BURN,
        n_score=DEFAULT_N_SCORE,
    )
    p0 = run_seed_channel_profit(
        seed,
        channels_for_preset("P0"),
        n_burn=DEFAULT_N_BURN,
        n_score=DEFAULT_N_SCORE,
    )
    assert oracle["profit"] != p0["profit"]
