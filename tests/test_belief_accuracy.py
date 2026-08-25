"""Tests for belief distribution MAE (nb19 / studio parity)."""

from __future__ import annotations

import numpy as np
import pytest

from blueberries_voi.experiments.belief_accuracy import (
    DISPLAY_BIN_COUNT,
    aggregate_belief_masses,
    centers_to_edges,
    day_distribution_abs_error,
    display_bin_masses_for_belief_and_units,
    distribution_abs_error,
    histogram_edges,
    rebin_masses_by_interval,
    truth_masses_from_units,
)

FLAT_BELIEF = {
    "L": 3,
    "K": 4,
    "lot_counts": [10, 6, 4],
    "f_grid": [0.125, 0.375, 0.625, 0.875],
    "f_marginals": [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    ],
}

UNITS = [{"unit_id": i, "lot_id": 1, "f": 0.3} for i in range(10)]


def test_centers_to_edges_matches_studio_pattern() -> None:
    edges = centers_to_edges([0.125, 0.375, 0.625, 0.875])
    assert edges.size == 5
    assert edges[0] < 0.125
    assert edges[-1] > 0.875


def test_aggregate_belief_masses_sums_lot_weighted_bins() -> None:
    masses = aggregate_belief_masses(FLAT_BELIEF)
    assert masses.shape == (4,)
    assert float(masses[0]) == 10.0


def test_histogram_edges_count() -> None:
    edges = histogram_edges(0.0, 1.0, DISPLAY_BIN_COUNT)
    assert edges.size == DISPLAY_BIN_COUNT + 1
    assert float(edges[0]) == 0.0
    assert float(edges[-1]) == 1.0


def test_distribution_abs_error_normalized_l1() -> None:
    belief = np.array([1.0, 1.0, 0.0, 0.0])
    truth = np.array([1.0, 0.0, 1.0, 0.0])
    mae = distribution_abs_error(belief, truth)
    assert mae is not None
    assert mae == 0.25


def test_truth_masses_from_units_bins_by_f() -> None:
    edges = histogram_edges(0.0, 1.0, 4)
    masses = truth_masses_from_units(UNITS, edges)
    assert float(masses.sum()) == len(UNITS)


def test_display_bin_masses_for_belief_and_units() -> None:
    belief_bins, truth_bins = display_bin_masses_for_belief_and_units(
        FLAT_BELIEF, UNITS
    )
    assert belief_bins.size == DISPLAY_BIN_COUNT
    assert truth_bins.size == DISPLAY_BIN_COUNT


def test_rebin_masses_by_interval_preserves_total() -> None:
    src_edges = np.array([0.0, 0.5, 1.0])
    src = np.array([2.0, 4.0])
    tgt_edges = histogram_edges(0.0, 1.0, 4)
    rebinned = rebin_masses_by_interval(src_edges, src, tgt_edges)
    assert float(rebinned.sum()) == pytest.approx(6.0)


def test_day_distribution_abs_error_from_delta() -> None:
    delta = {
        "belief": FLAT_BELIEF,
        "live_units": UNITS,
        "live_lots": [],
        "day": {},
    }
    mae = day_distribution_abs_error(delta)
    assert mae is not None
    assert mae >= 0.0
