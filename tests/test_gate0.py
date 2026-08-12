"""T-003: Abdella traces and Gate 0."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from blueberries_voi.model.abdella import (
    ABDELLA_PUBLISHED_DURATIONS_D,
    load_abdella_shipments,
    shipment_arrival_age,
)
from blueberries_voi.viz.gate0 import (
    gate0a_variance_decomposition,
    gate0b_caseround_sensitivity,
    run_gate0,
)

ROOT = Path(__file__).resolve().parents[1]
ABDELLA = ROOT / "data" / "abdella"


def test_six_shipments_present() -> None:
    ships = load_abdella_shipments(ABDELLA)
    assert len(ships) == 6
    assert {s.shipment_id for s in ships} == {f"S{i}" for i in range(1, 7)}


def test_empirical_durations_match_mod21_mix() -> None:
    ships = load_abdella_shipments(ABDELLA)
    durs = sorted(s.duration_d for s in ships)
    assert durs[0] >= 1.8
    assert durs[-1] <= 6.8
    # Roughly matches published 2.0-6.6 mix.
    assert any(1.8 <= d <= 2.3 for d in durs)
    assert any(6.0 <= d <= 6.8 for d in durs)


def test_missing_abdella_raises_not_synthetic(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"Missing Abdella|Abdella data"):
        load_abdella_shipments(tmp_path)


def test_arrival_age_spread_nontrivial() -> None:
    ships = load_abdella_shipments(ABDELLA)
    ages = np.array([shipment_arrival_age(s) for s in ships])
    assert float(np.var(ages, ddof=1)) > 0.05
    assert float(np.percentile(ages, 75) - np.percentile(ages, 25)) > 0.2


def test_gate0_writes_figures(tmp_path: Path) -> None:
    g0a, g0b = run_gate0(abdella_root=ABDELLA, figures_dir=tmp_path)
    assert (tmp_path / "gate0_variance.png").is_file()
    assert (tmp_path / "gate0_caseround.png").is_file()
    assert g0a.var_total > 0.0
    assert isinstance(g0b.swallowed_by_caseround, bool)
    _ = gate0a_variance_decomposition(load_abdella_shipments(ABDELLA))
    _ = gate0b_caseround_sensitivity(g0a.arrival_ages)
    assert set(ABDELLA_PUBLISHED_DURATIONS_D) == {f"S{i}" for i in range(1, 7)}
