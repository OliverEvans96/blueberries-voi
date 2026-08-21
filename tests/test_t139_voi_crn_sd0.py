"""T-139 AC-6: Stage B must not shift VOI CRN profits at arrival_dispersion_sd=0."""

from __future__ import annotations

import math
import os

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

# T-138 implement tip baseline (seed=1, default params including sd=0).
_T138_BASELINE: dict[str, float] = {
    "P0": -607.5,
    "P1": -518.0,
    "F1": -518.0,
    "F1s": -518.0,
    "F2a": -542.0,
    "F2": -542.0,
    "B-state": -542.0,
}


@pytest.fixture
def rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


def test_voi_crn_sd_zero_matches_t138_baseline(rust_backend: None) -> None:
    profits = run_voi_crn_cell(
        scenarios=list(VOI_SCENARIOS),
        root_seed=1,
        beta=2.0,
        n_burn=2,
        n_score=8,
        filter_n=32,
        H=2,
        n_rollout_paths=2,
        lead_time=1,
    )
    for scenario in VOI_SCENARIOS:
        got = float(profits[scenario])
        want = _T138_BASELINE[scenario]
        assert math.isclose(got, want, rel_tol=0.0, abs_tol=1e-6), (
            f"{scenario}: got {got}, want {want}"
        )
