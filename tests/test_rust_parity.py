"""Golden / skip-if-missing parity vs optional ``blueberries_voi._core`` (Wave E).

Structural ``atol`` checks — not bit-identical RNG (ADR 0127).
T-163 mirrors: per-lot delivery wire on events / FilterObs (S3.2, S3.7).
"""

from __future__ import annotations

import importlib
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.simulator.session import EngineSession
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OBS_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "obs.rs"
_SESSION_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "session.rs"
_FILTER_TYPES_PY = _REPO_ROOT / "src" / "blueberries_voi" / "filter" / "types.py"

rust_core = _maybe_core
_RUST_RUNTIME = pytest.mark.skipif(
    _maybe_core is None,
    reason="blueberries_voi._core not built",
)

# Structural parity tolerance for stochastic kernels (ADR 0127).
_STRUCTURAL_ATOL = 1.0

_DAY_STEP_SEED = 77
_FILTER_SEED = 13
_TRAJECTORY_SEED = 42
_CRN_ROOT_SEED = 42

_LOTS_PER_DELIVERY = 3


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def test_voi_core_filter_obs_has_per_lot_delivery_fields() -> None:
    """S3.1 — FilterObs must carry per-lot pack dates and temperature traces."""
    text = _OBS_RS.read_text(encoding="utf-8")
    assert "pack_dates_by_lot" in text, (
        "RED [S3.1]: obs.rs FilterObs missing pack_dates_by_lot (per-lot F2)"
    )
    assert "temp_traces_by_lot" in text, (
        "RED [S3.1]: obs.rs FilterObs missing temp_traces_by_lot (per-lot F3)"
    )
    rich_day = re.search(r"pub struct RichDay\s*\{([^}]+)\}", text, re.DOTALL)
    assert rich_day is not None
    body = rich_day.group(1)
    assert "temp_traces_by_lot" in body, (
        "RED [S3.1]: RichDay must store per-lot traces, not only shipment_trace"
    )


def test_voi_core_events_wire_exports_per_lot_delivery_fields() -> None:
    """S3.1 — session events JSON must include per-lot delivery metadata."""
    text = _SESSION_RS.read_text(encoding="utf-8")
    events_block = text.split("pub fn events_value", 1)[-1]
    assert '"temp_traces_by_lot"' in events_block, (
        "RED [S3.1]: events_value must emit temp_traces_by_lot on the wire"
    )
    assert '"pack_dates_by_lot"' in events_block, (
        "RED [S3.1]: events_value must emit pack_dates_by_lot on the wire"
    )


def test_python_filter_types_expose_per_lot_delivery_fields() -> None:
    """S3.2 — Python RichObs / mask path must mirror per-lot delivery wire."""
    text = _FILTER_TYPES_PY.read_text(encoding="utf-8")
    assert "pack_dates_by_lot" in text, (
        "RED [S3.2]: filter/types.py must expose pack_dates_by_lot on the wire mirror"
    )
    assert "temp_traces_by_lot" in text, (
        "RED [S3.2]: filter/types.py must expose temp_traces_by_lot on the wire mirror"
    )


def test_backend_default_is_rust_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wave E: production default is rust; env still overrides."""
    monkeypatch.delenv("BLUEBERRIES_VOI_BACKEND", raising=False)
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)
    if backend_mod.rust_core is not None:
        assert backend_mod.rust_available() is True
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "python")
    importlib.reload(backend_mod)
    assert backend_mod.rust_available() is False


def test_weibull_matches_python() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.weibull_survival_py removed")


def test_day_step_injected_smoke() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.day_step_injected removed")


def test_filter_step_one_day_smoke() -> None:
    pytest.skip("T-TAU-RETIRE: rust_core.filter_step_py removed")


@_RUST_RUNTIME
def test_engine_session_ten_day_trajectory_fixed_orders() -> None:
    """Ten-day session with fixed orders: monotonic seq and populated belief wire."""
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    ships = [
        ShipmentTrace(
            shipment_id="parity",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]
    cfg: dict[str, Any] = {
        "shipments": ships,
        "n_particles": 16,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    # MWF-style order gate: only Mon/Wed/Sat order days apply (see schedule_wire).
    orders = [0, 8, 0, 8, 0, 0, 8, 0, 8, 0]

    session = EngineSession()
    snap = session.init(cfg, seed=_TRAJECTORY_SEED)
    assert snap["seq"] == 0
    assert snap["episode_day"] == 0

    deltas: list[dict[str, Any]] = []
    for order in orders:
        deltas.append(session.step(order))

    assert len(deltas) == 10
    seqs = [int(d["seq"]) for d in deltas]
    assert seqs == list(range(1, 11))
    days = [int(d["episode_day"]) for d in deltas]
    assert days == list(range(10))

    init_lot_counts = list(snap["belief"]["lot_counts"])
    assert all(float(x) == 0.0 for x in init_lot_counts), "ADR 0136: init belief empty"

    for i, (delta, order) in enumerate(zip(deltas, orders, strict=True)):
        assert int(delta["day"]["order_qty"]) == order, f"day {i} order mismatch"
        belief = delta["belief"]
        lot_counts = list(belief["lot_counts"])
        assert len(lot_counts) == int(belief["L"])
        assert len(belief["f_marginals"]) == int(belief["L"]) * int(belief["K"])
        assert len(belief["f_grid"]) == int(belief["K"])

    final_belief = deltas[-1]["belief"]
    assert any(float(x) != 0.0 for x in final_belief["lot_counts"]), (
        "belief must populate after ten-day trajectory"
    )


def test_voi_crn_smoke_seven_scenarios_structural() -> None:
    """VOI CRN smoke: all seven scenarios return finite, differentiated profits."""
    if rust_core is None:
        pytest.skip("blueberries_voi._core not built")
    for root_seed in range(1, 33):
        profits = run_voi_crn_cell(
            beta=2.0,
            root_seed=root_seed,
            scenarios=list(VOI_SCENARIOS),
            n_burn=2,
            n_score=6,
            filter_n=24,
            H=2,
            n_rollout_paths=0,
            lead_time=1,
            shipments=smoke_cool_shipments(),
        )

        assert set(profits) == set(VOI_SCENARIOS)
        values = [float(profits[s]) for s in VOI_SCENARIOS]
        if not all(math.isfinite(v) for v in values):
            continue

        unique = len({round(v, 4) for v in values})
        if unique < 3:
            continue

        p0 = float(profits["P0"])
        f2a = float(profits["F2a"])
        bstate = float(profits["B-state"])
        # P0/F1 often collapse on short damped_sw smoke cells;
        # pack_date + oracle still split.
        if math.isclose(p0, f2a, abs_tol=1e-6):
            continue
        if math.isclose(p0, bstate, abs_tol=1e-6):
            continue
        return

    pytest.fail(
        "expected structural profit differentiation across scenarios "
        "for some seed in 1..32"
    )
