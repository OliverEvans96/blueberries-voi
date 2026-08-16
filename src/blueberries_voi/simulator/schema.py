"""Wire-contract validators for Snapshot / DayDelta (ADR 0100 / T-045).

Hosts and OpenAPI (T-051) reuse these helpers against golden fixtures and live
``EngineSession`` payloads. Presentation fields (economics, PnL, ghost, heatmap,
nested density / ViewModel) are forbidden on the Python return path.

CAL-C1 (T-085) documents ``schedule`` + ``demand_summary`` on cold Snapshot;
shape is validated when present (required on live/golden payloads).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_FORBIDDEN_KEYS = frozenset(
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

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "f_marginals", "f_grid", "L", "K"})
_LEGACY_BELIEF_KEYS = frozenset({"age_marginals", "tau_grid"})
_SNAPSHOT_REQUIRED = frozenset(
    {"seq", "episode_day", "belief", "schedule", "demand_summary"}
)
_DAY_DELTA_REQUIRED = frozenset({"seq", "episode_day", "day", "drop_oldest"})
_SCHEDULE_WEEKDAY_KEYS = ("delivery_weekdays", "order_weekdays")


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


def _require_mapping(obj: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        msg = f"{label} must be a Mapping, got {type(obj).__name__}"
        raise TypeError(msg)
    return obj


def _reject_forbidden(obj: Mapping[str, Any], *, label: str) -> None:
    forbidden = _collect_keys(obj) & _FORBIDDEN_KEYS
    if forbidden:
        msg = (
            f"{label} contains forbidden presentation keys "
            f"{sorted(forbidden)} (ADR 0100)"
        )
        raise ValueError(msg)


def _is_nested_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def validate_flat_belief(obj: Mapping[str, Any], *, label: str = "belief") -> None:
    """Raise if ``obj`` is not a flat L / L*K / K f-native belief buffer."""
    belief = _require_mapping(obj, label=label)
    legacy = _LEGACY_BELIEF_KEYS & {str(k) for k in belief}
    if legacy:
        msg = (
            f"{label} must not expose legacy τ-wire keys "
            f"{sorted(legacy)} (forbidden on f-native wire)"
        )
        raise ValueError(msg)

    missing = _FLAT_BELIEF_KEYS - {str(k) for k in belief}
    if missing:
        msg = f"{label} missing flat belief fields {sorted(missing)}"
        raise KeyError(msg)

    try:
        l_dim = int(belief["L"])
        k_dim = int(belief["K"])
    except (TypeError, ValueError) as exc:
        msg = f"{label}.L and {label}.K must be integers"
        raise TypeError(msg) from exc

    lot_counts = belief["lot_counts"]
    f_marginals = belief["f_marginals"]
    f_grid = belief["f_grid"]

    if not _is_nested_sequence(lot_counts):
        msg = f"{label}.lot_counts must be a sequence of floats"
        raise TypeError(msg)
    if not _is_nested_sequence(f_marginals):
        msg = f"{label}.f_marginals must be a flat sequence of floats"
        raise TypeError(msg)
    if not _is_nested_sequence(f_grid):
        msg = f"{label}.f_grid must be a sequence of floats"
        raise TypeError(msg)

    for i, x in enumerate(f_marginals):
        if _is_nested_sequence(x):
            msg = f"{label}.f_marginals[{i}] is nested; wire requires flat L*K"
            raise TypeError(msg)

    if len(lot_counts) != l_dim:
        msg = f"{label}: len(lot_counts)={len(lot_counts)} != L={l_dim}"
        raise ValueError(msg)
    if len(f_marginals) != l_dim * k_dim:
        msg = f"{label}: len(f_marginals)={len(f_marginals)} != L*K={l_dim * k_dim}"
        raise ValueError(msg)
    if len(f_grid) != k_dim:
        msg = f"{label}: len(f_grid)={len(f_grid)} != K={k_dim}"
        raise ValueError(msg)

    for i, f_val in enumerate(f_grid):
        try:
            fv = float(f_val)
        except (TypeError, ValueError) as exc:
            msg = f"{label}.f_grid[{i}] must be a number"
            raise TypeError(msg) from exc
        if fv < 0.0 or fv > 1.0:
            msg = f"{label}.f_grid[{i}]={fv} outside freshness [0, 1]"
            raise ValueError(msg)


def _validate_weekday_list(value: Any, *, label: str) -> None:
    if not _is_nested_sequence(value):
        msg = f"{label} must be a sequence of weekday ints (monday0 0..6)"
        raise TypeError(msg)
    if len(value) == 0:
        msg = f"{label} must be non-empty"
        raise ValueError(msg)
    for i, day in enumerate(value):
        try:
            d = int(day)
        except (TypeError, ValueError) as exc:
            msg = f"{label}[{i}] must be an int weekday"
            raise TypeError(msg) from exc
        if d < 0 or d > 6:
            msg = f"{label}[{i}]={d} out of monday0 range 0..6"
            raise ValueError(msg)


def _validate_schedule(obj: Any, *, label: str = "Snapshot.schedule") -> None:
    schedule = _require_mapping(obj, label=label)
    for key in _SCHEDULE_WEEKDAY_KEYS:
        if key not in schedule:
            msg = f"{label} missing {key}"
            raise KeyError(msg)
        _validate_weekday_list(schedule[key], label=f"{label}.{key}")
    lead = schedule.get("lead_time_days", schedule.get("lead_time"))
    if lead is None:
        msg = f"{label} must expose lead_time_days (or lead_time)"
        raise KeyError(msg)
    try:
        int(lead)
    except (TypeError, ValueError) as exc:
        msg = f"{label}.lead_time_days must be an int"
        raise TypeError(msg) from exc
    epoch = schedule.get("epoch")
    if not isinstance(epoch, str) or not epoch.strip():
        msg = f"{label}.epoch must be a non-empty date string"
        raise TypeError(msg)


def _validate_demand_summary(
    obj: Any, *, label: str = "Snapshot.demand_summary"
) -> None:
    summary = _require_mapping(obj, label=label)
    scale = summary.get("scale_mu", summary.get("scale_target_mu"))
    if scale is None:
        msg = f"{label} must expose scale_mu (or scale_target_mu)"
        raise KeyError(msg)
    try:
        scale_f = float(scale)
    except (TypeError, ValueError) as exc:
        msg = f"{label}.scale_mu must be a number"
        raise TypeError(msg) from exc
    if scale_f <= 0.0:
        msg = f"{label}.scale_mu must be positive"
        raise ValueError(msg)
    dow = summary.get("dow_means", summary.get("dow_factors"))
    if not _is_nested_sequence(dow):
        msg = f"{label} must expose dow_means or dow_factors sequence"
        raise TypeError(msg)
    if len(dow) != 7:
        msg = f"{label} DOW series must have length 7, got {len(dow)}"
        raise ValueError(msg)
    for i, x in enumerate(dow):
        try:
            xf = float(x)
        except (TypeError, ValueError) as exc:
            msg = f"{label} DOW[{i}] must be a number"
            raise TypeError(msg) from exc
        if xf <= 0.0:
            msg = f"{label} DOW[{i}] must be positive"
            raise ValueError(msg)


def validate_snapshot(obj: Mapping[str, Any]) -> None:
    """Validate a cold Snapshot payload; raise on contract violation."""
    snap = _require_mapping(obj, label="Snapshot")
    missing = _SNAPSHOT_REQUIRED - {str(k) for k in snap}
    if missing:
        msg = f"Snapshot missing required keys {sorted(missing)}"
        raise KeyError(msg)
    _reject_forbidden(snap, label="Snapshot")
    belief = _require_mapping(snap["belief"], label="Snapshot.belief")
    validate_flat_belief(belief, label="Snapshot.belief")
    _validate_schedule(snap["schedule"], label="Snapshot.schedule")
    _validate_demand_summary(snap["demand_summary"], label="Snapshot.demand_summary")


def validate_day_delta(obj: Mapping[str, Any]) -> None:
    """Validate a hot DayDelta payload; raise on contract violation."""
    delta = _require_mapping(obj, label="DayDelta")
    missing = _DAY_DELTA_REQUIRED - {str(k) for k in delta}
    if missing:
        msg = f"DayDelta missing required keys {sorted(missing)}"
        raise KeyError(msg)
    _reject_forbidden(delta, label="DayDelta")

    day = delta["day"]
    if not isinstance(day, Mapping):
        msg = f"DayDelta.day must be a Mapping, got {type(day).__name__}"
        raise TypeError(msg)

    drop = delta["drop_oldest"]
    if not isinstance(drop, bool):
        msg = f"DayDelta.drop_oldest must be bool, got {type(drop).__name__}"
        raise TypeError(msg)

    if "belief" in delta and delta["belief"] is not None:
        belief = _require_mapping(delta["belief"], label="DayDelta.belief")
        validate_flat_belief(belief, label="DayDelta.belief")


__all__ = [
    "validate_day_delta",
    "validate_flat_belief",
    "validate_snapshot",
]
