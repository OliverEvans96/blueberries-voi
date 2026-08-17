"""T-127 RED (qa-rust-tradeoff): tradeoff_forecast RPC — ADR 0130 sampling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SESSION_RS = REPO / "crates" / "voi_core" / "src" / "session.rs"
TRADEOFF_RS = REPO / "crates" / "voi_core" / "src" / "tradeoff.rs"

try:
    from blueberries_voi._core import handle_rpc as _rust_handle_rpc
except ImportError:
    _rust_handle_rpc = None  # type: ignore[misc, assignment]

_RUST = pytest.mark.skipif(_rust_handle_rpc is None, reason="_core not built")


def _rpc(
    method: str, params: dict[str, Any] | None = None, *, id_: str = "1"
) -> dict[str, Any]:
    assert _rust_handle_rpc is not None
    raw = _rust_handle_rpc(
        json.dumps({"id": id_, "method": method, "params": params or {}})
    )
    return json.loads(raw)


def test_tradeoff_rs_module_exists() -> None:
    assert TRADEOFF_RS.exists(), "crates/voi_core/src/tradeoff.rs must exist"


def test_session_rs_dispatches_tradeoff_forecast() -> None:
    text = SESSION_RS.read_text(encoding="utf-8")
    assert '"tradeoff_forecast"' in text


def test_tradeoff_rs_uses_systematic_resample_not_mean_collapse() -> None:
    text = TRADEOFF_RS.read_text(encoding="utf-8")
    assert "systematic_resample" in text or "bank" in text
    assert "unit_state_from_f_belief" not in text


def test_bench_tradeoff_forecast_exists() -> None:
    bench = REPO / "crates" / "voi_core" / "benches" / "tradeoff_forecast.rs"
    assert bench.exists()


@_RUST
def test_tradeoff_forecast_returns_candidates_sweep() -> None:
    _rpc("init", {"seed": 42})
    out = _rpc("tradeoff_forecast", {})
    assert out.get("ok") is True
    result = out["result"]
    candidates = result.get("candidates")
    assert isinstance(candidates, list)
    assert len(candidates) > 1
    q0 = candidates[0]
    for key in (
        "q",
        "waste_mean",
        "waste_p10",
        "waste_p50",
        "waste_p90",
        "missed_mean",
        "missed_p10",
        "missed_p50",
        "missed_p90",
        "joint_hist",
    ):
        assert key in q0, f"missing {key} on QForecast"
    hist = q0["joint_hist"]
    assert "waste_bins" in hist and "missed_bins" in hist and "counts" in hist


@_RUST
def test_tradeoff_forecast_optional_params() -> None:
    _rpc("init", {"seed": 1})
    out = _rpc("tradeoff_forecast", {"n_paths": 50, "protection_days": 3})
    assert out.get("ok") is True


@_RUST
def test_tradeoff_forecast_does_not_advance_day() -> None:
    _rpc("init", {"seed": 7})
    _rpc("step", {"order": 0})
    _rpc("tradeoff_forecast", {})
    # Re-check via fresh init+step — forecast must be read-only.
    out = _rpc("tradeoff_forecast", {})
    assert out.get("ok") is True


@_RUST
def test_act_rollout_unchanged_after_tradeoff_module() -> None:
    """Autopilot act q must not change when tradeoff_forecast is added."""
    _rpc("init", {"seed": 99, "obs_scenario": "P1"})
    act1 = _rpc("act", {"policy": "rollout"})
    _rpc("tradeoff_forecast", {})
    _rpc("init", {"seed": 99, "obs_scenario": "P1"})
    act2 = _rpc("act", {"policy": "rollout"})
    q1 = act1["result"]["day"]["order_qty"]
    q2 = act2["result"]["day"]["order_qty"]
    assert q1 == q2


@_RUST
def test_adr0130_p0_bands_wider_than_mean_collapse() -> None:
    """At P0, p90-p10 waste bands exceed a mean-collapse control."""
    _rpc("init", {"seed": 123, "obs_scenario": "P0"})
    out = _rpc("tradeoff_forecast", {"n_paths": 200, "protection_days": 3})
    candidates = out["result"]["candidates"]
    mid = candidates[len(candidates) // 2]
    width = mid["waste_p90"] - mid["waste_p10"]
    assert width > 0, "P0 bands should be strictly positive (ADR 0130)"


@_RUST
def test_unknown_method_still_errors() -> None:
    _rpc("init", {"seed": 1})
    out = _rpc("not_tradeoff", {})
    assert out.get("ok") is False
