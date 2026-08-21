"""T-140: VOI CRN profit snapshot under unified gamma arrival (ADR 0141)."""

from __future__ import annotations

import math

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

# T-140 implement tip (seed=1, default params, gamma arrival).
_T140_BASELINE: dict[str, float] = {
    "P0": 103.0,
    "P1": 153.0,
    "F1": 153.0,
    "F1s": 153.0,
    "F2a": 153.0,
    "F2": 153.0,
    "B-state": 205.0,
}


@pytest.fixture
def rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


def test_voi_crn_gamma_arrival_baseline(rust_backend: None) -> None:
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
        want = _T140_BASELINE[scenario]
        assert math.isclose(got, want, rel_tol=0.0, abs_tol=1e-6), (
            f"{scenario}: got {got}, want {want}"
        )
