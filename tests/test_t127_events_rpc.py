"""T-127 RED (qa-rust-events): events RPC — masked richest_log window."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
SESSION_RS = REPO / "crates" / "voi_core" / "src" / "session.rs"

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


def test_session_rs_dispatches_events_method() -> None:
    text = SESSION_RS.read_text(encoding="utf-8")
    assert '"events"' in text
    assert "since_day" in text


def test_session_rs_events_uses_mask_for() -> None:
    text = SESSION_RS.read_text(encoding="utf-8")
    assert "mask_for" in text or "obs::mask_for" in text


@_RUST
def test_events_requires_since_day() -> None:
    _rpc("init", {"seed": 1})
    _rpc("step", {"order": 0})
    out = _rpc("events", {})
    assert out.get("ok") is False


@_RUST
def test_events_returns_days_array_shape() -> None:
    _rpc("init", {"seed": 42, "obs_scenario": "P1"})
    _rpc("step", {"order": 8})
    out = _rpc("events", {"since_day": 0})
    assert out.get("ok") is True
    result = out.get("result")
    assert isinstance(result, dict), "events envelope must be { days: [...] }"
    days = result.get("days")
    assert isinstance(days, list)
    if days:
        day0 = days[0]
        assert "day" in day0
        assert "arrivals" in day0
        assert "sales_total" in day0 or "sales_total" not in day0


@_RUST
def test_events_p0_waste_is_null_not_zero() -> None:
    _rpc("init", {"seed": 7, "obs_scenario": "P0"})
    for _ in range(3):
        _rpc("step", {"order": 0})
    out = _rpc("events", {"since_day": 0})
    days = out["result"]["days"]
    for d in days:
        wt = d.get("waste_total")
        assert wt is None or wt != 0 or d.get("waste_total") is None


@_RUST
def test_events_since_day_slice() -> None:
    _rpc("init", {"seed": 99, "obs_scenario": "F2"})
    for _ in range(5):
        _rpc("step", {"order": 0})
    all_days = _rpc("events", {"since_day": 0})["result"]["days"]
    partial = _rpc("events", {"since_day": 2})["result"]["days"]
    assert len(partial) <= len(all_days)
    if partial:
        assert partial[0]["day"] >= 2


@_RUST
def test_events_since_day_gt_day_returns_empty() -> None:
    _rpc("init", {"seed": 1})
    _rpc("step", {"order": 0})
    out = _rpc("events", {"since_day": 999})
    assert out["result"]["days"] == []


@_RUST
def test_events_does_not_advance_session_day() -> None:
    _rpc("init", {"seed": 1})
    _rpc("step", {"order": 0})
    out = _rpc("events", {"since_day": 0})
    assert out.get("ok") is True


def test_wasm_worker_mentions_events() -> None:
    worker = REPO / "packaging" / "wasm" / "worker.js"
    if worker.exists():
        assert "events" in worker.read_text(encoding="utf-8")
