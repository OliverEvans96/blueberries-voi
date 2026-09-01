"""T-135: ObsChannels scan parity with Rust (T-163 per-lot delivery wire)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from blueberries_voi.filter.types import (
    ObsChannels,
    channels_cache_key,
    channels_for_preset,
    mask_for,
    mask_from_channels,
    validate_channels,
)
from blueberries_voi.simulator.belief import empty_flat_belief
from blueberries_voi.simulator.session import EngineSession

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OBS_MASK_TS = _REPO_ROOT / "web" / "src" / "obsMask.ts"
_ENGINE_TYPES_TS = _REPO_ROOT / "web" / "src" / "engine" / "types.ts"

_FLAT = empty_flat_belief(L=2, K=4)
_LOTS_PER_DELIVERY = 3


def _config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "seed": 1,
        "n_particles": 32,
        "enable_filter": True,
        "shipments": [{"times_d": [0.0, 1.0, 2.0], "temps_c": [5.0, 5.0, 5.0]}],
        "obs_scenario": "P1",
    }
    cfg.update(overrides)
    return cfg


def _snap(obs_channels: ObsChannels, obs: str = "P1") -> dict[str, Any]:
    return {
        "seq": 0,
        "episode_day": 0,
        "belief": dict(_FLAT),
        "applied_config": {
            "obs_scenario": obs,
            "obs_channels": {
                "code_type": obs_channels.code_type,
                "scan_waste": obs_channels.scan_waste,
                "delivery_history": obs_channels.delivery_history,
            },
        },
        "history": [],
        "live_lots": [],
        "pipeline": [],
    }


class _FakePyEngineSession:
    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.set_obs_channels_calls: list[tuple[str, bool, str]] = []

    def init(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _snap(channels_for_preset("P1"))

    def set_obs_channels(
        self, code_type: str, scan_waste: bool, delivery_history: str
    ) -> dict[str, Any]:
        self.set_obs_channels_calls.append((code_type, scan_waste, delivery_history))
        ch = ObsChannels(
            code_type=code_type,  # type: ignore[arg-type]
            scan_waste=scan_waste,
            delivery_history=delivery_history,  # type: ignore[arg-type]
        )
        return _snap(ch, obs="F2a")


def _install_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, _FakePyEngineSession]:
    holder: dict[str, _FakePyEngineSession] = {}

    def factory(seed: int = 0) -> _FakePyEngineSession:
        sess = _FakePyEngineSession(seed)
        holder["s"] = sess
        return sess

    fake = SimpleNamespace(PyEngineSession=factory)
    monkeypatch.setattr("blueberries_voi.backend.rust_available", lambda: True)
    monkeypatch.setattr("blueberries_voi.backend.rust_core", fake)
    return holder


PRESET_IDS = ("P0", "P1", "F1", "F1s", "F2a", "F2", "F3")

ALL_CHANNELS: tuple[ObsChannels, ...] = tuple(
    ObsChannels(code_type=code, scan_waste=scan_waste, delivery_history=hist)
    for code in ("upc", "lgtin")
    for scan_waste in (False, True)
    for hist in ("none", "pack_date", "temperature_history")
)


def present_set(mask) -> frozenset[str]:
    return mask.present


def test_mask_from_channels_all_twelve_combos() -> None:
    for ch in ALL_CHANNELS:
        mask = mask_from_channels(ch)
        present = present_set(mask)
        assert "arrivals" in present and "sales_total" in present
        if ch.code_type == "lgtin":
            assert {"sales_by_lot", "lot_ids_live", "arrival_lot_ids"} <= present
        else:
            assert "sales_by_lot" not in present
            assert "arrival_lot_ids" not in present
        if not ch.scan_waste:
            assert "waste_total" not in present
        elif ch.code_type == "upc":
            assert "waste_total" in present
            assert "waste_by_lot" not in present
        else:
            assert {"waste_total", "waste_by_lot"} <= present
        if ch.delivery_history == "pack_date":
            assert "pack_date" in present
            assert "temperature_history" not in present
        elif ch.delivery_history == "temperature_history":
            assert "temperature_history" in present
            assert "pack_date" not in present
        else:
            assert "pack_date" not in present
            assert "temperature_history" not in present
        assert "age_at_receipt" not in present


def test_preset_round_trip_matches_mask_for_without_age() -> None:
    for sid in PRESET_IDS:
        ch = channels_for_preset(sid)
        from_channels = mask_from_channels(ch)
        from_id = mask_for(sid)
        assert from_channels.present == from_id.present
        assert "age_at_receipt" not in from_channels.present


def test_f2_preset_uses_pack_date_not_age() -> None:
    ch = channels_for_preset("F2")
    assert ch.code_type == "lgtin" and ch.scan_waste
    assert ch.delivery_history == "pack_date"
    mask = mask_from_channels(ch)
    assert "pack_date" in mask.present
    assert "age_at_receipt" not in mask.present


def test_f1s_matches_f1_under_scan_model() -> None:
    assert channels_for_preset("F1s") == channels_for_preset("F1")


def test_channels_cache_key_canonical() -> None:
    ch = ObsChannels(code_type="lgtin", scan_waste=True, delivery_history="none")
    assert channels_cache_key(ch) == "code=lgtin|waste=1|hist=none"


def test_validate_channels_rejects_unknown_enum() -> None:
    with pytest.raises(ValueError, match="code_type"):
        validate_channels(
            {"code_type": "invalid", "scan_waste": False, "delivery_history": "none"}
        )
    with pytest.raises(ValueError, match="delivery_history"):
        validate_channels(
            {"code_type": "upc", "scan_waste": False, "delivery_history": "bad"}
        )


def test_set_obs_channels_on_session(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_config(), seed=42)
    ch = ObsChannels(
        code_type="upc",
        scan_waste=True,
        delivery_history="pack_date",
    )
    snap = session.set_obs_channels(ch)
    applied = snap["applied_config"]
    assert applied["obs_channels"]["delivery_history"] == "pack_date"
    assert applied["obs_scenario"] == "F2a"
    inner = holder["s"]
    assert inner.set_obs_channels_calls == [("upc", True, "pack_date")]


def test_typescript_rich_obs_wire_has_per_lot_delivery_fields() -> None:
    """S3.3 — TS mirror must expose per-lot pack dates and traces on the events wire."""
    obs_mask = _OBS_MASK_TS.read_text(encoding="utf-8")
    engine_types = _ENGINE_TYPES_TS.read_text(encoding="utf-8")
    assert "pack_dates_by_lot" in obs_mask, (
        "RED [S3.3]: obsMask RichObsWire must carry pack_dates_by_lot"
    )
    assert "pack_dates_by_lot" in engine_types, (
        "RED [S3.3]: engine/types EventDayWire must carry pack_dates_by_lot"
    )
    assert "temp_traces_by_lot" in engine_types


def test_f3_mask_keeps_per_lot_trace_array_not_scalar_only() -> None:
    """S3.3 — F3 temperature history must prefer per-lot trace arrays on the wire."""
    obs_mask = _OBS_MASK_TS.read_text(encoding="utf-8")
    apply_block = obs_mask.split("export function applyMask", 1)[-1]
    assert "temp_traces_by_lot" in apply_block
    assert "pack_dates_by_lot" in apply_block, (
        "RED [S3.3]: applyMask must gate pack_dates_by_lot when pack_date mask is on"
    )


def test_delivery_arrival_lot_ids_expect_three_lots_per_delivery() -> None:
    """S3.2/S3.3 — multi-lot deliveries mint three arrival lot ids (L=3 contract)."""
    text = (_REPO_ROOT / "crates" / "voi_core" / "src" / "session.rs").read_text(
        encoding="utf-8"
    )
    assert "LOTS_PER_DELIVERY" in text or "lots_per_delivery" in text, (
        "RED [S3.2]: session must define lots-per-delivery constant (expected 3)"
    )
    assert str(_LOTS_PER_DELIVERY) in text, (
        f"RED [S3.2]: expected lots-per-delivery constant {_LOTS_PER_DELIVERY}"
    )
