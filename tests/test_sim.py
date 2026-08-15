"""T-004 / T-009: arrival generator, forward simulator, rich DayLog."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from blueberries_voi import model, sim
from blueberries_voi.model import ModelParams, day_step
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import EpisodeLog, open_loop_order, run_episode

_F3_OPEN_LOOP = (
    "T-121 F3: ADR 0127 Wave F supersession — Python open-loop day_step removed"
)

ROOT = Path(__file__).resolve().parents[1]
ABDELLA = ROOT / "data" / "abdella"


def test_sim_shares_day_step() -> None:
    """ENG-02: filter and sim import the shared model.day_step (T-009 AC)."""
    assert sim.day_step is model.day_step
    assert day_step.__module__ == "blueberries_voi.sim.rust_bridge"


def test_open_loop_base_stock() -> None:
    assert open_loop_order(40, S=60) == 20
    assert open_loop_order(60, S=60) == 0
    assert open_loop_order(70, S=60) == 0


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_episode_smoke_finite() -> None:
    ships = load_abdella_shipments(ABDELLA)
    ep = run_episode(
        ModelParams(),
        root_seed=1,
        run_id="smoke",
        n_burn=10,
        n_score=30,
        shipments=ships,
    )
    scored = ep.scored
    assert len(scored) == 30
    inv = [sum(lot.n for lot in d.lots) for d in scored]
    waste = [d.waste_total for d in scored]
    assert all(np.isfinite(inv))
    assert all(w >= 0 for w in waste)
    Ls = [d.L for d in scored]
    assert max(Ls) >= 1


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_spread_scale_tightens() -> None:
    ships = load_abdella_shipments(ABDELLA)
    full = run_episode(
        root_seed=2,
        run_id="sp",
        n_burn=5,
        n_score=40,
        spread_scale=1.0,
        shipments=ships,
    )
    tight = run_episode(
        root_seed=2,
        run_id="sp",
        n_burn=5,
        n_score=40,
        spread_scale=0.05,
        shipments=ships,
    )
    [lot.tau for d in full.scored for lot in d.lots if d.arrivals and lot]
    # Compare arrival ages recorded on delivery days via newest lot.
    af = []
    at = []
    for df, dt in zip(full.days, tight.days, strict=True):
        if df.arrivals > 0 and df.lots:
            af.append(df.lots[-1].tau)
            at.append(dt.lots[-1].tau)
    assert float(np.std(af)) > float(np.std(at))


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_p1_obs_fields_present() -> None:
    ships = load_abdella_shipments(ABDELLA)
    ep = run_episode(n_burn=2, n_score=5, shipments=ships, root_seed=3)
    d = ep.days[2]
    assert hasattr(d, "sales_total")
    assert hasattr(d, "waste_total")
    assert hasattr(d, "arrivals")
    assert hasattr(d, "L")


# --- T-009 Rich DayLog / SIM-04 emit ---


def _short_episode(*, root_seed: int = 11, run_id: str = "t009") -> EpisodeLog:
    ships = load_abdella_shipments(ABDELLA)
    return run_episode(
        ModelParams(),
        root_seed=root_seed,
        run_id=run_id,
        n_burn=5,
        n_score=20,
        shipments=ships,
    )


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_daylog_sales_waste_by_lot_maps() -> None:
    """Each DayLog exposes per-lot sales/waste maps keyed by lot_id."""
    ep = _short_episode()
    assert ep.days, "episode must log at least one day"
    for d in ep.days:
        assert isinstance(d.sales_by_lot, dict)
        assert isinstance(d.waste_by_lot, dict)
        for lid, qty in d.sales_by_lot.items():
            assert isinstance(lid, int)
            assert isinstance(qty, (int, np.integer))
            assert int(qty) >= 0
        for lid, qty in d.waste_by_lot.items():
            assert isinstance(lid, int)
            assert isinstance(qty, (int, np.integer))
            assert int(qty) >= 0


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_daylog_lots_keep_n_tau_lot_id() -> None:
    """End-of-day live lots still carry n, tau, and lot_id."""
    ep = _short_episode()
    seen_live = False
    for d in ep.days:
        assert isinstance(d.lots, list)
        for lot in d.lots:
            seen_live = True
            assert hasattr(lot, "n") and isinstance(lot.n, (int, np.integer))
            assert hasattr(lot, "tau") and isinstance(lot.tau, (float, np.floating))
            assert hasattr(lot, "lot_id") and isinstance(lot.lot_id, (int, np.integer))
            assert int(lot.n) > 0
    assert seen_live, "expected at least one live lot across the episode"


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_daylog_receipt_metadata_delivery_vs_none() -> None:
    """Delivery days expose age_at_receipt; non-delivery leave receipt fields None."""
    ep = _short_episode(root_seed=12)
    saw_delivery = False
    saw_non_delivery = False
    for d in ep.days:
        assert hasattr(d, "age_at_receipt")
        assert hasattr(d, "pack_date")
        if d.arrivals > 0:
            saw_delivery = True
            assert d.age_at_receipt is not None
            assert isinstance(d.age_at_receipt, (float, np.floating))
            assert float(d.age_at_receipt) >= 0.0
            # Must not be zeroed as a stand-in for "unset".
            assert d.age_at_receipt is not False
            # T-019 / Oliver: delivery days must emit ASN pack_date (not optional).
            assert d.pack_date is not None, (
                "delivery DayLog.pack_date must be a real date (T-019)"
            )
            assert isinstance(d.pack_date, date)
            # New delivery tau_in should match the newest live lot when present.
            if d.lots:
                assert abs(float(d.lots[-1].tau) - float(d.age_at_receipt)) < 1e-12
        else:
            saw_non_delivery = True
            assert d.age_at_receipt is None
            assert d.pack_date is None
    assert saw_delivery, "fixture episode must include at least one delivery day"
    assert saw_non_delivery, "fixture episode must include a non-delivery day"


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_daylog_totals_match_by_lot_sums() -> None:
    """sales_total / waste_total equal the sum of per-lot maps; empty when zero."""
    ep = _short_episode(root_seed=13)
    saw_positive_sales = False
    saw_zero_sales = False
    for d in ep.days:
        assert d.sales_total == sum(d.sales_by_lot.values())
        assert d.waste_total == sum(d.waste_by_lot.values())
        if d.sales_total == 0:
            saw_zero_sales = True
            assert d.sales_by_lot == {}
        else:
            saw_positive_sales = True
            assert d.sales_by_lot
        if d.waste_total == 0:
            assert d.waste_by_lot == {}
        else:
            assert d.waste_by_lot
    assert saw_positive_sales, "expected some day with positive sales"
    assert saw_zero_sales, "expected some day with zero sales (empty map)"


@pytest.mark.skip(reason=_F3_OPEN_LOOP)
def test_daylog_crn_scored_aggregates_stable() -> None:
    """Identical (root_seed, run_id, params) → identical scored aggregates (CRN)."""
    ships = load_abdella_shipments(ABDELLA)
    a = run_episode(
        ModelParams(),
        root_seed=42,
        run_id="crn-t009",
        n_burn=8,
        n_score=25,
        shipments=ships,
    )
    b = run_episode(
        ModelParams(),
        root_seed=42,
        run_id="crn-t009",
        n_burn=8,
        n_score=25,
        shipments=ships,
    )
    assert len(a.days) == len(b.days)
    for da, db in zip(a.days, b.days, strict=True):
        assert da.sales_total == db.sales_total
        assert da.waste_total == db.waste_total
        assert da.arrivals == db.arrivals
        assert da.demand == db.demand
        assert da.L == db.L
