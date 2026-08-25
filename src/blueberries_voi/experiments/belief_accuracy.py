"""Belief accuracy metrics aligned with studio ``beliefAccuracy.ts`` (nb19)."""

from __future__ import annotations

from typing import Any

import numpy as np

DISPLAY_BIN_COUNT = 8

__all__ = [
    "DISPLAY_BIN_COUNT",
    "aggregate_belief_masses",
    "centers_to_edges",
    "day_distribution_abs_error",
    "display_bin_masses_for_belief_and_units",
    "distribution_abs_error",
    "histogram_edges",
    "rebin_masses_by_interval",
    "truth_masses_from_units",
]


def centers_to_edges(centers: np.ndarray | list[float]) -> np.ndarray:
    """Map filter bin centers to half-open interval edges (studio projector)."""
    c = np.asarray(centers, dtype=float)
    if c.size == 0:
        return np.array([], dtype=float)
    if c.size == 1:
        val = float(c[0])
        return np.array([val, val + 1.0], dtype=float)
    edges: list[float] = [float(c[0] - (c[1] - c[0]) / 2.0)]
    for i in range(c.size - 1):
        edges.append(float((c[i] + c[i + 1]) / 2.0))
    last = float(c[-1])
    prev = float(c[-2])
    edges.append(last + (last - prev) / 2.0)
    return np.asarray(edges, dtype=float)


def histogram_edges(
    lo: float, hi: float, bin_count: int = DISPLAY_BIN_COUNT
) -> np.ndarray:
    """Evenly spaced histogram edges over ``[lo, hi]``."""
    return np.linspace(lo, hi, bin_count + 1, dtype=float)


def aggregate_belief_masses(belief: dict[str, Any]) -> np.ndarray:
    """Sum belief mass across lots for each freshness bin."""
    lot_counts = np.asarray(belief["lot_counts"], dtype=float)
    f_marginals = np.asarray(belief["f_marginals"], dtype=float)
    l_count = int(belief["L"])
    k_count = len(belief["f_grid"])
    masses = np.zeros(k_count, dtype=float)
    for ell in range(l_count):
        count = float(lot_counts[ell])
        for k in range(k_count):
            masses[k] += count * float(f_marginals[ell * k_count + k])
    return masses


def _bin_index_for_value(edges: np.ndarray, value: float) -> int:
    n = edges.size - 1
    if n <= 0:
        return 0
    if value <= float(edges[0]):
        return 0
    if value >= float(edges[n]):
        return n - 1
    for i in range(n):
        if value < float(edges[i + 1]):
            return i
    return n - 1


def rebin_masses_by_interval(
    source_edges: np.ndarray,
    source_masses: np.ndarray,
    target_edges: np.ndarray,
) -> np.ndarray:
    """Rebin source interval masses into target histogram bins."""
    bins = np.zeros(target_edges.size - 1, dtype=float)
    for i, mass in enumerate(source_masses):
        src_lo = float(source_edges[i])
        src_hi = float(source_edges[i + 1])
        width = src_hi - src_lo
        if width <= 0:
            continue
        for j in range(bins.size):
            tgt_lo = float(target_edges[j])
            tgt_hi = float(target_edges[j + 1])
            overlap = max(0.0, min(src_hi, tgt_hi) - max(src_lo, tgt_lo))
            bins[j] += float(mass) * (overlap / width)
    return bins


def truth_masses_from_units(
    units: list[dict[str, Any]],
    edges: np.ndarray,
) -> np.ndarray:
    """Count live units into histogram bins by each unit's ``f``."""
    bins = np.zeros(edges.size - 1, dtype=float)
    for unit in units:
        idx = _bin_index_for_value(edges, float(unit["f"]))
        bins[idx] += 1.0
    return bins


def distribution_abs_error(
    belief_masses: np.ndarray,
    truth_masses: np.ndarray,
) -> float | None:
    """(1/K) sum_k |p_k - q_k| on normalized unit-count shares."""
    belief_total = float(belief_masses.sum())
    truth_total = float(truth_masses.sum())
    if belief_total <= 0 or truth_total <= 0:
        return None
    k = belief_masses.size
    if k == 0 or truth_masses.size != k:
        return None
    sum_abs = 0.0
    for i in range(k):
        p = float(belief_masses[i]) / belief_total
        q = float(truth_masses[i]) / truth_total
        sum_abs += abs(p - q)
    return sum_abs / k


def display_bin_masses_for_belief_and_units(
    belief: dict[str, Any],
    units: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray]:
    """Eight display bins on ``[0, 1]`` for belief vs truth unit masses."""
    f_grid = np.asarray(belief["f_grid"], dtype=float)
    f_edges = centers_to_edges(f_grid)
    belief_masses = aggregate_belief_masses(belief)
    display_edges = histogram_edges(0.0, 1.0, DISPLAY_BIN_COUNT)
    belief_bins = rebin_masses_by_interval(f_edges, belief_masses, display_edges)
    truth_bins = truth_masses_from_units(units, display_edges)
    return belief_bins, truth_bins


def day_distribution_abs_error(delta: dict[str, Any]) -> float | None:
    """Distribution MAE for one scored day from delta wire payload."""
    units = delta.get("live_units")
    if not units:
        return None
    belief = delta.get("belief")
    if not belief:
        return None
    belief_bins, truth_bins = display_bin_masses_for_belief_and_units(belief, units)
    return distribution_abs_error(belief_bins, truth_bins)
