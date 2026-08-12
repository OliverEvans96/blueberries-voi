"""T-004: arrival generator and forward simulator."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from blueberries_voi import filter as filter_pkg
from blueberries_voi import model, sim
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import open_loop_order, run_episode

ROOT = Path(__file__).resolve().parents[1]
ABDELLA = ROOT / "data" / "abdella"


def test_sim_shares_day_step() -> None:
    assert sim.day_step is model.day_step
    assert filter_pkg.day_step is model.day_step


def test_open_loop_base_stock() -> None:
    assert open_loop_order(40, S=60) == 20
    assert open_loop_order(60, S=60) == 0
    assert open_loop_order(70, S=60) == 0


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


def test_p1_obs_fields_present() -> None:
    ships = load_abdella_shipments(ABDELLA)
    ep = run_episode(n_burn=2, n_score=5, shipments=ships, root_seed=3)
    d = ep.days[2]
    assert hasattr(d, "sales_total")
    assert hasattr(d, "waste_total")
    assert hasattr(d, "arrivals")
    assert hasattr(d, "L")
