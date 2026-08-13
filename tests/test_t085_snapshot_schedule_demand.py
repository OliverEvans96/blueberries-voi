"""T-085: Snapshot schedule + demand_summary wire (CAL-C1) — RED before implement.

Locks ``.team/specs/T-085.md``: cold Snapshot / init config exposes OrderSchedule
fields + a chart-ready demand profile summary; mock adapter stubs coherent values;
golden / contract tests document new keys without ViewModel/PnL leakage (ADR 0100).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession
from blueberries_voi.simulator.schema import validate_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "simulator"
_SNAPSHOT_GOLDEN = _FIXTURE_DIR / "snapshot_seed42.json"
_FIXTURE_README = _FIXTURE_DIR / "README.md"
_DEMAND_PROFILE = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"

_FIXED_SEED = 42
_EPOCH = "2024-01-01"
_DEFAULT_DELIVERY = frozenset({0, 2, 4})
_DEFAULT_ORDER = frozenset({6, 1, 3})
_DEFAULT_LEAD = 1

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "economics",
        "pnl_series",
        "pnl_totals",
        "ghost",
        "ghost_deltas",
        "heatmap",
        "density",
        "ViewModel",
        "view_model",
    }
)


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T085-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T085-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _session_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return cfg


def _collect_keys(obj: Any, *, found: set[str] | None = None) -> set[str]:
    out = found if found is not None else set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            out.add(str(key))
            _collect_keys(value, found=out)
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            _collect_keys(item, found=out)
    return out


def _assert_no_forbidden(obj: Any, *, label: str) -> None:
    forbidden = _collect_keys(obj) & _FORBIDDEN_PAYLOAD_KEYS
    assert not forbidden, (
        f"{label} must not contain forbidden presentation keys "
        f"{sorted(forbidden)} (ADR 0100 / T-085)"
    )


def _weekday_list(values: Any) -> list[int]:
    assert isinstance(values, Sequence) and not isinstance(
        values, (str, bytes, bytearray)
    ), f"weekdays must be a sequence of ints, got {type(values).__name__}"
    out = [int(v) for v in values]
    assert out, "weekday list must be non-empty"
    for d in out:
        assert 0 <= d <= 6, f"weekday {d} out of monday0 range 0..6"
    return out


def _assert_schedule_block(schedule: Any, *, label: str) -> Mapping[str, Any]:
    assert isinstance(schedule, Mapping), (
        f"{label} must be a mapping with delivery/order weekdays, lead time, epoch"
    )
    delivery = _weekday_list(schedule.get("delivery_weekdays"))
    order = _weekday_list(schedule.get("order_weekdays"))
    lead = schedule.get("lead_time_days", schedule.get("lead_time"))
    assert lead is not None, (
        f"{label} must expose lead_time_days (or lead_time) for UI cadence"
    )
    assert int(lead) == _DEFAULT_LEAD, (
        f"{label} lead_time_days must default to {_DEFAULT_LEAD} (ADR 0111), got {lead!r}"  # noqa: E501
    )
    epoch = schedule.get("epoch")
    assert isinstance(epoch, str) and epoch.strip(), (
        f"{label} must expose epoch date string so UI can label weekdays from day index"
    )
    assert epoch.startswith("2024-01-01") or epoch == _EPOCH, (
        f"{label}.epoch must be calendar Monday {_EPOCH!r} (got {epoch!r})"
    )
    assert frozenset(delivery) == _DEFAULT_DELIVERY, (
        f"{label}.delivery_weekdays must be MWF {_DEFAULT_DELIVERY}, got {delivery!r}"
    )
    assert frozenset(order) == _DEFAULT_ORDER, (
        f"{label}.order_weekdays must be Sun/Tue/Thu {_DEFAULT_ORDER}, got {order!r}"
    )
    return schedule


def _assert_demand_summary(summary: Any, *, label: str) -> Mapping[str, Any]:
    assert isinstance(summary, Mapping), (
        f"{label} must be a mapping (chart-ready demand profile summary)"
    )
    scale = summary.get("scale_mu", summary.get("scale_target_mu"))
    assert scale is not None, (
        f"{label} must expose scale_mu (or scale_target_mu) for DOW charts"
    )
    assert float(scale) > 0.0, f"{label} scale must be positive, got {scale!r}"

    dow = summary.get("dow_means", summary.get("dow_factors"))
    assert isinstance(dow, Sequence) and not isinstance(dow, (str, bytes, bytearray)), (
        f"{label} must expose dow_means or dow_factors sequence"
    )
    assert len(dow) == 7, (
        f"{label} DOW series must have length 7 (monday0), got len={len(dow)}"
    )
    assert all(isinstance(x, (int, float)) and float(x) > 0.0 for x in dow), (
        f"{label} DOW entries must be positive numbers, got {list(dow)!r}"
    )
    # Summary is not the full FreshNet JSON blob.
    assert "week_factors" not in summary or "sku_ids" not in summary, (
        f"{label} should be a chart summary, not the full demand_profile.json blob"
    )
    return summary


def _schedule_from_snapshot(snap: Mapping[str, Any]) -> Any:
    if "schedule" in snap:
        return snap["schedule"]
    applied = snap.get("applied_config")
    if isinstance(applied, Mapping) and "schedule" in applied:
        return applied["schedule"]
    return None


def _demand_summary_from_snapshot(snap: Mapping[str, Any]) -> Any:
    if "demand_summary" in snap:
        return snap["demand_summary"]
    applied = snap.get("applied_config")
    if isinstance(applied, Mapping) and "demand_summary" in applied:
        return applied["demand_summary"]
    return None


# ---------------------------------------------------------------------------
# AC: Snapshot / init config exposes schedule fields
# ---------------------------------------------------------------------------


def test_live_snapshot_exposes_schedule_fields() -> None:
    """EngineSession.init Snapshot must carry OrderSchedule export for Studio."""
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    assert isinstance(snap, Mapping)
    schedule = _schedule_from_snapshot(snap)
    assert schedule is not None, (
        "Snapshot must expose schedule "
        "(top-level or under applied_config) with delivery_weekdays, "
        "order_weekdays, lead_time_days, and epoch (T-085 / ADR 0111)"
    )
    _assert_schedule_block(schedule, label="live Snapshot.schedule")
    _assert_no_forbidden(snap, label="live Snapshot")


def test_live_snapshot_schedule_matches_default_order_schedule() -> None:
    """Exported weekdays / LT must match DEFAULT_ORDER_SCHEDULE (no JS physics)."""
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    schedule = _schedule_from_snapshot(snap)
    assert schedule is not None, "Snapshot.schedule missing (T-085)"
    block = _assert_schedule_block(schedule, label="live Snapshot.schedule")
    assert frozenset(int(x) for x in block["delivery_weekdays"]) == frozenset(
        DEFAULT_ORDER_SCHEDULE.delivery_weekdays
    )
    assert frozenset(int(x) for x in block["order_weekdays"]) == frozenset(
        DEFAULT_ORDER_SCHEDULE.order_weekdays
    )
    lead = int(block.get("lead_time_days", block.get("lead_time")))
    assert lead == int(DEFAULT_ORDER_SCHEDULE.lead_time_days)


def test_live_snapshot_schedule_epoch_labels_monday0_weekdays() -> None:
    """Epoch must be enough for UI to map day index → weekday label."""
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    schedule = _schedule_from_snapshot(snap)
    assert schedule is not None, "Snapshot.schedule missing (T-085)"
    block = _assert_schedule_block(schedule, label="live Snapshot.schedule")
    # Day 0 under epoch 2024-01-01 is Monday (weekday 0); not an order day.
    assert 0 not in {int(x) for x in block["order_weekdays"]}
    assert DEFAULT_ORDER_SCHEDULE.can_order(0) is False
    assert DEFAULT_ORDER_SCHEDULE.can_order(1) is True  # Tue


# ---------------------------------------------------------------------------
# AC: demand profile summary for charts
# ---------------------------------------------------------------------------


def test_live_snapshot_exposes_demand_summary() -> None:
    """Snapshot must expose chart-ready demand_summary (not full JSON blob)."""
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    summary = _demand_summary_from_snapshot(snap)
    assert summary is not None, (
        "Snapshot must expose demand_summary "
        "(top-level or under applied_config) with scale_mu and length-7 DOW series "
        "(T-085)"
    )
    _assert_demand_summary(summary, label="live Snapshot.demand_summary")
    _assert_no_forbidden(snap, label="live Snapshot")


def test_live_demand_summary_scale_near_committed_profile() -> None:
    """Summary scale should track committed FreshNet profile (~30), not invent physics."""  # noqa: E501
    assert _DEMAND_PROFILE.is_file(), "committed demand_profile.json required (T-080)"
    profile = json.loads(_DEMAND_PROFILE.read_text(encoding="utf-8"))
    expected_scale = float(profile["scale_target_mu"])

    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    summary = _demand_summary_from_snapshot(snap)
    assert summary is not None, "Snapshot.demand_summary missing (T-085)"
    block = _assert_demand_summary(summary, label="live Snapshot.demand_summary")
    scale = float(block.get("scale_mu", block.get("scale_target_mu")))
    assert abs(scale - expected_scale) <= 1.0, (
        f"demand_summary scale_mu={scale} must be within ±1 of profile "
        f"scale_target_mu={expected_scale}"
    )


def test_demand_summary_is_not_full_freshnet_blob() -> None:
    """Wire summary must stay slim — no SKU list / provenance dump on Snapshot."""
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    summary = _demand_summary_from_snapshot(snap)
    assert summary is not None, "Snapshot.demand_summary missing (T-085)"
    blob_keys = {"sku_ids", "hf_revision", "fit_utc", "censoring", "dataset_id"}
    present = blob_keys & set(summary)
    assert not present, (
        f"demand_summary must not ship full FreshNet product keys {sorted(present)}"
    )


# ---------------------------------------------------------------------------
# AC: golden / contract documents new keys; forbidden keys remain forbidden
# ---------------------------------------------------------------------------


def test_snapshot_golden_documents_schedule_and_demand_summary() -> None:
    """Committed Snapshot golden must document schedule + demand_summary keys."""
    assert _SNAPSHOT_GOLDEN.is_file(), f"missing golden {_SNAPSHOT_GOLDEN.name}"
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    assert isinstance(golden, dict)
    schedule = _schedule_from_snapshot(golden)
    assert schedule is not None, (
        f"{_SNAPSHOT_GOLDEN.name} must document schedule fields (T-085 contract)"
    )
    _assert_schedule_block(schedule, label="Snapshot golden.schedule")
    summary = _demand_summary_from_snapshot(golden)
    assert summary is not None, (
        f"{_SNAPSHOT_GOLDEN.name} must document demand_summary (T-085 contract)"
    )
    _assert_demand_summary(summary, label="Snapshot golden.demand_summary")
    validate_snapshot(golden)
    _assert_no_forbidden(golden, label="Snapshot golden")


def test_fixture_readme_documents_schedule_and_demand_summary() -> None:
    """Fixture README must name the new Snapshot keys for implement/UI consumers."""
    assert _FIXTURE_README.is_file()
    text = _FIXTURE_README.read_text(encoding="utf-8").lower()
    assert "schedule" in text, "fixture README must document Snapshot schedule"
    assert "demand_summary" in text or "demand summary" in text, (
        "fixture README must document Snapshot demand_summary"
    )
    assert "forbidden" in text or "presentation" in text


def test_live_snapshot_keyset_includes_golden_schedule_keys() -> None:
    """Live init must include at least the golden's schedule / demand_summary keys."""
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    session = EngineSession()
    snap = session.init(_session_config(), seed=_FIXED_SEED)
    assert isinstance(snap, Mapping)
    validate_snapshot(snap)
    # After golden update, live payloads must grow to cover documented keys.
    assert set(snap.keys()) >= set(golden.keys()) or (
        _schedule_from_snapshot(snap) is not None
        and _demand_summary_from_snapshot(snap) is not None
    ), (
        "live Snapshot keys must cover golden contract including schedule + "
        f"demand_summary; golden={sorted(golden.keys())} live={sorted(snap.keys())}"
    )
    assert _schedule_from_snapshot(snap) is not None
    assert _demand_summary_from_snapshot(snap) is not None


def test_validate_snapshot_still_rejects_pnl_on_schedule_bearing_payload() -> None:
    """ADR 0100 preserved: schedule/demand_summary do not relax forbidden keys."""
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    dirty = dict(golden)
    dirty["pnl_totals"] = {"profit": 1.0}
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        validate_snapshot(dirty)


# ---------------------------------------------------------------------------
# Unhappy / boundary (schema must reject malformed new fields)
# ---------------------------------------------------------------------------


def test_validate_snapshot_rejects_schedule_with_out_of_range_weekday() -> None:
    """Boundary: weekday integers outside monday0 0..6 are invalid on the wire."""
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    dirty = dict(golden)
    dirty["schedule"] = {
        "delivery_weekdays": [0, 2, 7],
        "order_weekdays": [6, 1, 3],
        "lead_time_days": 1,
        "epoch": _EPOCH,
    }
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        validate_snapshot(dirty)


def test_validate_snapshot_rejects_demand_summary_with_wrong_dow_length() -> None:
    """Boundary: DOW series length must be exactly 7 (not 6 / 8)."""
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    dirty = dict(golden)
    dirty["demand_summary"] = {"scale_mu": 30.0, "dow_means": [1.0] * 6}
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        validate_snapshot(dirty)


def test_validate_snapshot_rejects_empty_order_weekdays() -> None:
    """Unhappy: empty order_weekdays is not a usable Studio schedule."""
    golden = json.loads(_SNAPSHOT_GOLDEN.read_text(encoding="utf-8"))
    dirty = dict(golden)
    dirty["schedule"] = {
        "delivery_weekdays": [0, 2, 4],
        "order_weekdays": [],
        "lead_time_days": 1,
        "epoch": _EPOCH,
    }
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        validate_snapshot(dirty)
