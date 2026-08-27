"""F-native belief wire at EngineSession boundary (ADR 0131 / T-163 mirrors)."""

from __future__ import annotations

from pathlib import Path

import pytest

from blueberries_voi.filter.belief import ShelfBelief, shelf_belief_from_oracle
from blueberries_voi.model import Cohort
from blueberries_voi.simulator.belief import (
    empty_flat_belief,
    f_grid_k,
    flatten_shelf_belief,
    live_lots_payload,
    pipeline_payload,
    shelf_belief_from_flat,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BELIEF_FLAT_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "belief_flat.rs"


def test_f_grid_k_centers_in_unit_interval() -> None:
    assert f_grid_k(0) == []
    assert f_grid_k(1) == [0.0]
    assert f_grid_k(4) == [0.0, pytest.approx(1 / 3), pytest.approx(2 / 3), 1.0]


def test_f_grid_k_rejects_negative_k() -> None:
    with pytest.raises(ValueError, match="K must be non-negative"):
        f_grid_k(-1)


def test_empty_flat_belief_uniform_rows() -> None:
    flat = empty_flat_belief(L=2, K=3)
    assert flat["L"] == 2
    assert flat["K"] == 3
    assert flat["lot_counts"] == [0.0, 0.0]
    assert len(flat["f_marginals"]) == 6
    assert flat["f_grid"] == [0.0, 0.5, 1.0]


def test_empty_flat_belief_rejects_l_positive_k_zero() -> None:
    with pytest.raises(ValueError, match="K must be >= 1"):
        empty_flat_belief(L=1, K=0)


def test_flatten_and_round_trip_oracle_belief() -> None:
    grid = [0.0, 1.0]
    belief = shelf_belief_from_oracle(
        lot_counts=[5],
        f_marginals=[[1.0, 0.0]],
        f_grid=grid,
    )
    flat = flatten_shelf_belief(belief)
    rebuilt = shelf_belief_from_flat(flat)
    assert isinstance(rebuilt, ShelfBelief)
    assert rebuilt.lot_counts == belief.lot_counts
    assert rebuilt.f_marginals == belief.f_marginals
    assert rebuilt.f_grid == belief.f_grid


def test_live_lots_payload_mean_f_from_tau() -> None:
    cohorts = [
        Cohort(n=0, tau=1.0, lot_id=1),
        Cohort(n=10, tau=7.0, lot_id=2),
    ]
    lots = live_lots_payload(cohorts)
    assert len(lots) == 1
    assert lots[0]["lot_id"] == 2
    assert lots[0]["n"] == 10
    assert lots[0]["mean_f"] == pytest.approx(0.5)


def test_pipeline_payload_sorted_nonzero() -> None:
    assert pipeline_payload({3: 5, 1: 0, 2: 4}) == [
        {"arrival_day": 2, "qty": 4},
        {"arrival_day": 3, "qty": 5},
    ]


def test_belief_flat_wire_stays_f_native_without_tau_keys() -> None:
    """S3.1 — belief_flat.rs exports f-grid wire only (no legacy τ keys)."""
    production = _BELIEF_FLAT_RS.read_text(encoding="utf-8").split("#[cfg(test)]", 1)[0]
    export_fn = production.split("pub fn belief_flat_from_unit_bank", 1)[1]
    assert '"f_grid"' in export_fn and '"f_marginals"' in export_fn
    assert '"tau_grid"' not in export_fn
    assert '"age_marginals"' not in export_fn


def test_belief_flat_does_not_embed_scalar_delivery_trace_fields() -> None:
    """S3.1 — per-lot delivery metadata belongs on events/FilterObs, not belief_flat."""
    text = _BELIEF_FLAT_RS.read_text(encoding="utf-8")
    export_block = text.split("pub fn belief_flat_from_unit_bank", 1)[-1]
    assert "temp_traces_by_lot" not in export_block, (
        "belief_flat must not duplicate per-lot delivery traces (events wire owns them)"
    )
    assert "pack_dates_by_lot" not in export_block
