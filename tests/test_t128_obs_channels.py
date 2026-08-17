"""T-128 RED: ObsChannels mask_from_channels parity with preset ladder."""

from __future__ import annotations

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

_FLAT = empty_flat_belief(L=2, K=4)


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
                "pos": obs_channels.pos,
                "waste": obs_channels.waste,
                "deliveries": obs_channels.deliveries,
            },
        },
        "history": [],
        "live_lots": [],
        "pipeline": [],
    }


class _FakePyEngineSession:
    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.set_obs_channels_calls: list[tuple[str, str, str]] = []

    def init(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _snap(channels_for_preset("P1"))

    def set_obs_channels(self, pos: str, waste: str, deliveries: str) -> dict[str, Any]:
        self.set_obs_channels_calls.append((pos, waste, deliveries))
        ch = ObsChannels(pos=pos, waste=waste, deliveries=deliveries)
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


PRESET_IDS = ("P0", "P1", "F1", "F1s", "F2a", "F2")

# All 12 orthogonal combos (pos x waste x deliveries).
ALL_CHANNELS: tuple[ObsChannels, ...] = tuple(
    ObsChannels(pos=pos, waste=waste, deliveries=delivery)
    for pos in ("upc_only", "lot_id")
    for waste in ("none", "daily_counts", "lot_id")
    for delivery in ("quantity_only", "pack_date_per_lot")
)


def present_set(mask) -> frozenset[str]:
    return mask.present


def test_mask_from_channels_all_twelve_combos() -> None:
    for ch in ALL_CHANNELS:
        mask = mask_from_channels(ch)
        present = present_set(mask)
        assert "arrivals" in present and "sales_total" in present
        if ch.pos == "lot_id":
            assert "sales_by_lot" in present and "lot_ids_live" in present
        else:
            assert "sales_by_lot" not in present
        if ch.waste == "none":
            assert "waste_total" not in present
        elif ch.waste == "daily_counts":
            assert "waste_total" in present
            assert "waste_by_lot" not in present
        else:
            assert "waste_total" in present and "waste_by_lot" in present
            assert "lot_ids_live" in present
        if ch.deliveries == "pack_date_per_lot":
            assert "pack_date" in present
        else:
            assert "pack_date" not in present
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
    assert ch.pos == "lot_id" and ch.waste == "lot_id"
    assert ch.deliveries == "pack_date_per_lot"
    mask = mask_from_channels(ch)
    assert "pack_date" in mask.present
    assert "age_at_receipt" not in mask.present


def test_channels_cache_key_canonical() -> None:
    ch = ObsChannels(pos="lot_id", waste="daily_counts", deliveries="quantity_only")
    expected = "pos=lot_id|waste=daily_counts|deliveries=quantity_only"
    assert channels_cache_key(ch) == expected


def test_validate_channels_rejects_unknown_enum() -> None:
    with pytest.raises(ValueError, match="pos"):
        validate_channels(
            {"pos": "invalid", "waste": "none", "deliveries": "quantity_only"}
        )
    with pytest.raises(ValueError, match="waste"):
        validate_channels(
            {"pos": "upc_only", "waste": "bad", "deliveries": "quantity_only"}
        )
    with pytest.raises(ValueError, match="deliveries"):
        validate_channels({"pos": "upc_only", "waste": "none", "deliveries": "bad"})


def test_set_obs_channels_on_session(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _install_fake(monkeypatch)
    session = EngineSession()
    session.init(_config(), seed=42)
    ch = ObsChannels(
        pos="upc_only",
        waste="daily_counts",
        deliveries="pack_date_per_lot",
    )
    snap = session.set_obs_channels(ch)
    applied = snap["applied_config"]
    assert applied["obs_channels"]["deliveries"] == "pack_date_per_lot"
    assert applied["obs_scenario"] == "F2a"
    inner = holder["s"]
    assert inner.set_obs_channels_calls == [
        ("upc_only", "daily_counts", "pack_date_per_lot"),
    ]
