"""T-131 f-native PyO3 helper parity (non-rollout). Rollout MC tests removed."""

from __future__ import annotations

import pytest

from blueberries_voi.backend import rust_available, rust_core
from blueberries_voi.model import ModelParams, weibull_survival
from blueberries_voi.sim.bakeoff_rollout import (
    detect_crn_desync,
    terminal_salvage_value,
    w_long_oldest_first,
)

pytestmark = pytest.mark.skipif(
    not rust_available() or rust_core is None,
    reason="requires blueberries_voi._core",
)


def test_w_long_weibull_helper_matches_python_on_fixture() -> None:
    """PyO3 Weibull helpers match cohort bakeoff_rollout (fallback path only)."""
    assert rust_core is not None
    lots = (
        {"n": 4, "tau": 6.0},
        {"n": 2, "tau": 2.0},
        {"n": 1, "tau": 0.0},
    )
    margin = 2.0
    params = ModelParams()
    py_vt = terminal_salvage_value(lots, margin=margin, params=params)
    weights = w_long_oldest_first(lots, params=params)
    freshness = []
    for lot in lots:
        n = int(lot["n"])
        tau = float(lot["tau"])
        f_val = max(0.0, 1.0 - tau / float(params.eta_ref))
        freshness.extend([f_val] * n)
    rust_vt = float(
        rust_core.terminal_salvage_unit_state_py(
            freshness,
            margin,
            float(params.beta),
            float(params.eta_ref),
        )
    )
    assert rust_vt == pytest.approx(py_vt, rel=0.0, abs=1e-9)
    for tau, w in zip((6.0, 2.0, 0.0), weights, strict=True):
        rust_w = float(
            rust_core.w_long_py(tau, float(params.beta), float(params.eta_ref))
        )
        assert rust_w == pytest.approx(
            weibull_survival(tau, beta=params.beta, eta=params.eta_ref),
            rel=0.0,
            abs=1e-12,
        )
        assert rust_w == pytest.approx(w, rel=0.0, abs=1e-12)


def test_detect_crn_desync_gate() -> None:
    """ENG-04: matching stream addresses agree; crossed streams desync."""
    addr_a = {
        "root_seed": 11,
        "run_id": "t131-crn",
        "day": 0,
        "stream": ":demand",
    }
    addr_b = dict(addr_a)
    ok_match = detect_crn_desync(address_a=addr_a, address_b=addr_b)
    assert ok_match.ok
    addr_crossed = dict(addr_a)
    addr_crossed["stream"] = ":spoil"
    ok_cross = detect_crn_desync(address_a=addr_a, address_b=addr_crossed)
    assert not ok_cross.ok


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
