"""T-140: VOI CRN profit snapshot under unified gamma arrival (ADR 0141)."""

from __future__ import annotations

import math

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

# T-150 f-native arrival physics; schema-2 arrival_model.json (v2 generative drift).
_T150_BASELINE: dict[str, float] = {
    "P0": 270.5,
    "P1": 270.5,
    "F1": 270.5,
    "F1s": 270.5,
    "F2a": 262.0,
    "F2": 262.0,
    "B-state": 230.5,
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
        n_rollout_paths=0,
        lead_time=1,
    )
    for scenario in VOI_SCENARIOS:
        got = float(profits[scenario])
        want = _T150_BASELINE[scenario]
        assert math.isclose(got, want, rel_tol=0.0, abs_tol=1e-6), (
            f"{scenario}: got {got}, want {want}"
        )
