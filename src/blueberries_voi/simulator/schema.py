"""Wire-contract validators for Snapshot / DayDelta (ADR 0098 / T-045).

Hosts and OpenAPI (T-051) reuse these helpers against golden fixtures and live
``EngineSession`` payloads. Presentation fields (economics, PnL, ghost, heatmap,
nested density / ViewModel) are forbidden on the Python return path.
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

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "age_marginals", "tau_grid", "L", "K"})
_SNAPSHOT_REQUIRED = frozenset({"seq", "episode_day", "belief"})
_DAY_DELTA_REQUIRED = frozenset({"seq", "episode_day", "day", "drop_oldest"})


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
            f"{sorted(forbidden)} (ADR 0098)"
        )
        raise ValueError(msg)


def _is_nested_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def validate_flat_belief(obj: Mapping[str, Any], *, label: str = "belief") -> None:
    """Raise if ``obj`` is not a flat L / L*K / K belief buffer."""
    belief = _require_mapping(obj, label=label)
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
    age_marginals = belief["age_marginals"]
    tau_grid = belief["tau_grid"]

    if not _is_nested_sequence(lot_counts):
        msg = f"{label}.lot_counts must be a sequence of floats"
        raise TypeError(msg)
    if not _is_nested_sequence(age_marginals):
        msg = f"{label}.age_marginals must be a flat sequence of floats"
        raise TypeError(msg)
    if not _is_nested_sequence(tau_grid):
        msg = f"{label}.tau_grid must be a sequence of floats"
        raise TypeError(msg)

    if len(lot_counts) != l_dim:
        msg = f"{label}: len(lot_counts)={len(lot_counts)} != L={l_dim}"
        raise ValueError(msg)
    if len(age_marginals) != l_dim * k_dim:
        msg = f"{label}: len(age_marginals)={len(age_marginals)} != L*K={l_dim * k_dim}"
        raise ValueError(msg)
    if len(tau_grid) != k_dim:
        msg = f"{label}: len(tau_grid)={len(tau_grid)} != K={k_dim}"
        raise ValueError(msg)

    for i, x in enumerate(age_marginals):
        if _is_nested_sequence(x):
            msg = f"{label}.age_marginals[{i}] is nested; wire requires flat L*K"
            raise TypeError(msg)


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
