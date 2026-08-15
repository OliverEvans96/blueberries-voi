"""T-121d Wave D: VOI CRN observation masks via Rust backend (RED).

Proves ``crates/voi_core/src/voi.rs`` applies full ``obs::mask_for`` ladders
(not the ``mask_obs`` aggregate stub). Python reference: ``voi/crn.py`` +
``filter/types.py``.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.voi import run_voi_crn_cell

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

# Structural parity: profits may differ in last bits vs Python, but scenario
# differentiation must exceed noise when masks diverge (ADR 0127 / Wave D).
_STRUCTURAL_ATOL = 1e-6

_ROOT_SEED = 42
_N_BURN = 2
_N_SCORE = 8
_FILTER_N = 32
_H = 2
_N_ROLLOUT_PATHS = 2
_LEAD_TIME = 1
_BETA = 2.0


@pytest.fixture
def rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


def _crn_cell_kwargs() -> dict[str, Any]:
    return {
        "beta": _BETA,
        "root_seed": _ROOT_SEED,
        "n_burn": _N_BURN,
        "n_score": _N_SCORE,
        "filter_n": _FILTER_N,
        "H": _H,
        "n_rollout_paths": _N_ROLLOUT_PATHS,
        "lead_time": _LEAD_TIME,
        "shipments": smoke_cool_shipments(),
    }


def test_rust_crn_p0_profit_differs_from_f1(rust_backend: None) -> None:
    """P0 (aggregate sales only) must not match F1 (lot-resolved sales) on same CRN."""
    profits = run_voi_crn_cell(scenarios=["P0", "F1"], **_crn_cell_kwargs())
    p0 = float(profits["P0"])
    f1 = float(profits["F1"])
    assert math.isfinite(p0) and math.isfinite(f1)
    assert not math.isclose(p0, f1, rel_tol=0.0, abs_tol=_STRUCTURAL_ATOL), (
        f"P0 and F1 profits must differ under distinct observation masks "
        f"(got P0={p0}, F1={f1})"
    )


def test_rust_crn_f2_profit_differs_from_p1(rust_backend: None) -> None:
    """F2 (lot-resolved sales+waste+age) must not collapse to P1 (aggregate totals)."""
    profits = run_voi_crn_cell(scenarios=["P1", "F2"], **_crn_cell_kwargs())
    p1 = float(profits["P1"])
    f2 = float(profits["F2"])
    assert math.isfinite(p1) and math.isfinite(f2)
    assert not math.isclose(p1, f2, rel_tol=0.0, abs_tol=_STRUCTURAL_ATOL), (
        f"F2 must differ from P1 when lot-resolved masks are wired "
        f"(got P1={p1}, F2={f2})"
    )
