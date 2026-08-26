"""Filter types, RichObs / UNOBSERVED masks, and P1 observation contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

# Memory budget: K^L * N floats (FIL-13 / T-005).
MAX_JOINT_FLOATS: float = 5.0e7

AGE_GRID_LO: float = 0.0
AGE_GRID_HI: float = 8.0

ScenarioId: TypeAlias = Literal["P0", "P1", "F1", "F1s", "F2a", "F2", "F3"]

CodeType: TypeAlias = Literal["upc", "gsin"]
DeliveryHistory: TypeAlias = Literal["none", "pack_date", "temperature_history"]

_RICH_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "arrivals",
        "sales_total",
        "waste_total",
        "sales_by_lot",
        "waste_by_lot",
        "pack_date",
        "age_at_receipt",
        "lot_ids_live",
        "arrival_lot_ids",
        "pack_dates_by_lot",
        "temp_traces_by_lot",
        "temperature_history",
    }
)

# ADR 0086 present-field table (global scan model presets).
_SCENARIO_PRESENT: dict[ScenarioId, frozenset[str]] = {
    "P0": frozenset({"arrivals", "sales_total"}),
    "P1": frozenset({"arrivals", "sales_total", "waste_total"}),
    "F1": frozenset(
        {
            "arrivals",
            "sales_total",
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "lot_ids_live",
            "arrival_lot_ids",
        }
    ),
    "F1s": frozenset(
        {
            "arrivals",
            "sales_total",
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "lot_ids_live",
            "arrival_lot_ids",
        }
    ),
    "F2a": frozenset({"arrivals", "sales_total", "waste_total", "pack_date"}),
    "F2": frozenset(
        {
            "arrivals",
            "sales_total",
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "pack_date",
            "lot_ids_live",
            "arrival_lot_ids",
        }
    ),
    "F3": frozenset(
        {
            "arrivals",
            "sales_total",
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "lot_ids_live",
            "arrival_lot_ids",
            "temperature_history",
        }
    ),
}

_PRESET_CHANNELS: dict[ScenarioId, dict[str, str | bool]] = {
    "P0": {
        "code_type": "upc",
        "scan_waste": False,
        "delivery_history": "none",
    },
    "P1": {
        "code_type": "upc",
        "scan_waste": True,
        "delivery_history": "none",
    },
    "F1": {
        "code_type": "gsin",
        "scan_waste": True,
        "delivery_history": "none",
    },
    "F1s": {
        "code_type": "gsin",
        "scan_waste": True,
        "delivery_history": "none",
    },
    "F2a": {
        "code_type": "upc",
        "scan_waste": True,
        "delivery_history": "pack_date",
    },
    "F2": {
        "code_type": "gsin",
        "scan_waste": True,
        "delivery_history": "pack_date",
    },
    "F3": {
        "code_type": "gsin",
        "scan_waste": True,
        "delivery_history": "temperature_history",
    },
}


class Unobserved:
    """Singleton sentinel: field absent under a scenario mask (≠ 0 / {} / None)."""

    __slots__ = ()
    _instance: Unobserved | None = None

    def __new__(cls) -> Unobserved:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNOBSERVED"

    def __bool__(self) -> bool:
        return False


UNOBSERVED: Final[Unobserved] = Unobserved()
UnobservedT: TypeAlias = Unobserved


def is_unobserved(value: object) -> bool:
    """True iff ``value`` is the ``UNOBSERVED`` sentinel."""
    return value is UNOBSERVED


@dataclass(frozen=True)
class ObsChannels:
    """Global scan observation channels."""

    code_type: CodeType
    scan_waste: bool
    delivery_history: DeliveryHistory


def validate_channels(raw: Mapping[str, object] | ObsChannels) -> ObsChannels:
    """Parse and validate channel enums from a mapping."""
    if isinstance(raw, ObsChannels):
        return raw
    code_type = str(raw.get("code_type", ""))
    scan_waste = bool(raw.get("scan_waste", False))
    delivery_history = str(raw.get("delivery_history", ""))
    if code_type not in ("upc", "gsin"):
        msg = f"invalid code_type: {code_type!r}"
        raise ValueError(msg)
    if delivery_history not in ("none", "pack_date", "temperature_history"):
        msg = f"invalid delivery_history: {delivery_history!r}"
        raise ValueError(msg)
    return ObsChannels(
        code_type=code_type,  # type: ignore[arg-type]
        scan_waste=scan_waste,
        delivery_history=delivery_history,  # type: ignore[arg-type]
    )


def channels_for_preset(scenario: ScenarioId | str) -> ObsChannels:
    if scenario == "B-state":
        msg = (
            "SCN-B-state is a verification bypass, not an ObsMask; "
            "do not fabricate observations via mask_for"
        )
        raise ValueError(msg)
    if scenario not in _PRESET_CHANNELS:
        msg = f"Unknown scenario for ObsMask: {scenario!r}"
        raise KeyError(msg)
    return validate_channels(_PRESET_CHANNELS[scenario])


_PRESET_IDS: tuple[ScenarioId, ...] = (
    "P0",
    "P1",
    "F1",
    "F1s",
    "F2a",
    "F2",
    "F3",
)


def preset_for_channels(channels: ObsChannels) -> ScenarioId | None:
    """Return the named ladder preset matching ``channels``, or ``None`` if custom."""
    for sid in _PRESET_IDS:
        preset = channels_for_preset(sid)
        if (
            preset.code_type == channels.code_type
            and preset.scan_waste == channels.scan_waste
            and preset.delivery_history == channels.delivery_history
        ):
            return sid
    return None


def channels_cache_key(channels: ObsChannels) -> str:
    waste = "1" if channels.scan_waste else "0"
    return f"code={channels.code_type}|waste={waste}|hist={channels.delivery_history}"


def mask_from_channels(channels: ObsChannels) -> ObsMask:
    present: set[str] = {"arrivals", "sales_total"}
    if channels.code_type == "gsin":
        present.update({"sales_by_lot", "lot_ids_live", "arrival_lot_ids"})
    if channels.scan_waste:
        present.add("waste_total")
        if channels.code_type == "gsin":
            present.add("waste_by_lot")
    if channels.delivery_history == "pack_date":
        present.add("pack_date")
        present.add("pack_dates_by_lot")
    elif channels.delivery_history == "temperature_history":
        present.add("temperature_history")
        present.add("temp_traces_by_lot")
    return ObsMask(present=frozenset(present))


@dataclass(frozen=True)
class P1Obs:
    sales_total: int
    waste_total: int
    arrivals: int


@dataclass(frozen=True)
class RichObs:
    """Richest filter observation; absent fields use ``UNOBSERVED`` (ADR 0086)."""

    arrivals: int | Unobserved
    sales_total: int | Unobserved
    waste_total: int | Unobserved
    sales_by_lot: Mapping[int, int] | Unobserved
    waste_by_lot: Mapping[int, int] | Unobserved
    pack_date: date | Unobserved
    pack_dates_by_lot: tuple[int, ...] | Unobserved
    temp_traces_by_lot: tuple[object, ...] | Unobserved
    age_at_receipt: float | Unobserved
    lot_ids_live: frozenset[int] | Unobserved

    @classmethod
    def from_p1(cls, obs: P1Obs) -> RichObs:
        """Compatibility constructor: P1 totals present; richer fields unobserved."""
        return cls(
            arrivals=obs.arrivals,
            sales_total=obs.sales_total,
            waste_total=obs.waste_total,
            sales_by_lot=UNOBSERVED,
            waste_by_lot=UNOBSERVED,
            pack_date=UNOBSERVED,
            pack_dates_by_lot=UNOBSERVED,
            temp_traces_by_lot=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )


@dataclass(frozen=True)
class ObsMask:
    """Which RichObs fields are present for a data-availability rung."""

    present: frozenset[str]

    def __post_init__(self) -> None:
        unknown = self.present - _RICH_FIELD_NAMES
        if unknown:
            msg = f"ObsMask.present has unknown field names: {sorted(unknown)}"
            raise ValueError(msg)

    def apply(self, rich: RichObs) -> RichObs:
        """Keep present fields; set all others to ``UNOBSERVED`` (never 0 / {})."""
        present = self.present
        return RichObs(
            arrivals=rich.arrivals if "arrivals" in present else UNOBSERVED,
            sales_total=rich.sales_total if "sales_total" in present else UNOBSERVED,
            waste_total=rich.waste_total if "waste_total" in present else UNOBSERVED,
            sales_by_lot=rich.sales_by_lot if "sales_by_lot" in present else UNOBSERVED,
            waste_by_lot=rich.waste_by_lot if "waste_by_lot" in present else UNOBSERVED,
            pack_date=rich.pack_date if "pack_date" in present else UNOBSERVED,
            pack_dates_by_lot=(
                rich.pack_dates_by_lot if "pack_dates_by_lot" in present else UNOBSERVED
            ),
            temp_traces_by_lot=(
                rich.temp_traces_by_lot
                if "temp_traces_by_lot" in present
                else UNOBSERVED
            ),
            age_at_receipt=(
                rich.age_at_receipt if "age_at_receipt" in present else UNOBSERVED
            ),
            lot_ids_live=rich.lot_ids_live if "lot_ids_live" in present else UNOBSERVED,
        )


def mask_for(scenario: ScenarioId | str) -> ObsMask:
    """Return the ObsMask for a settled M1.5 scenario id (ADR 0133 preset compile)."""
    return mask_from_channels(channels_for_preset(scenario))


def _lot_ids_from_day(day: Any) -> frozenset[int] | Unobserved:
    lots = getattr(day, "lots", None)
    if lots is None:
        return UNOBSERVED
    ids: set[int] = set()
    for lot in lots:
        lot_id = getattr(lot, "lot_id", None)
        if lot_id is not None:
            ids.add(int(lot_id))
    return frozenset(ids)


def _optional_from_day(value: object) -> Any:
    """Map missing delivery metadata to UNOBSERVED; never invent 0 / 0.0."""
    if value is None or is_unobserved(value):
        return UNOBSERVED
    return value


def rich_obs_from_day_log(day: Any, mask: ObsMask) -> RichObs:
    """Project a DayLog (or DayLog-like stub) through ``mask`` into ``RichObs``.

    Hidden fields become ``UNOBSERVED``. Present optional delivery metadata that
    is ``None`` on the day is not invented as ``0`` / ``0.0``.
    """
    sales_by_lot = getattr(day, "sales_by_lot", UNOBSERVED)
    waste_by_lot = getattr(day, "waste_by_lot", UNOBSERVED)
    if sales_by_lot is None:
        sales_by_lot = UNOBSERVED
    if waste_by_lot is None:
        waste_by_lot = UNOBSERVED

    full = RichObs(
        arrivals=int(day.arrivals),
        sales_total=int(day.sales_total),
        waste_total=int(day.waste_total),
        sales_by_lot=sales_by_lot,
        waste_by_lot=waste_by_lot,
        pack_date=_optional_from_day(getattr(day, "pack_date", None)),
        pack_dates_by_lot=_optional_from_day(getattr(day, "pack_dates_by_lot", None)),
        temp_traces_by_lot=_optional_from_day(getattr(day, "temp_traces_by_lot", None)),
        age_at_receipt=_optional_from_day(getattr(day, "age_at_receipt", None)),
        lot_ids_live=_lot_ids_from_day(day),
    )
    return mask.apply(full)


@dataclass
class FilterSummary:
    ess: float
    mean_L: float
    log_lik: float


def age_grid(K: int) -> np.ndarray:
    if K < 2:
        msg = "K must be >= 2"
        raise ValueError(msg)
    return np.linspace(AGE_GRID_LO, AGE_GRID_HI, K)


def joint_state_count(K: int, L: int, N: int) -> float:
    return float(K**L) * float(N)


def guard_joint_memory(K: int, L: int, N: int) -> None:
    n = joint_state_count(K, L, N)
    if n > MAX_JOINT_FLOATS:
        msg = (
            f"Joint age posterior budget exceeded: "
            f"K^L*N={n:.3e} > {MAX_JOINT_FLOATS:.3e} "
            f"(K={K}, L={L}, N={N}). Escalate FIL-13 - do not silently truncate L."
        )
        raise MemoryError(msg)


__all__ = [
    "AGE_GRID_HI",
    "AGE_GRID_LO",
    "MAX_JOINT_FLOATS",
    "UNOBSERVED",
    "CodeType",
    "DeliveryHistory",
    "FilterSummary",
    "ObsChannels",
    "ObsMask",
    "P1Obs",
    "RichObs",
    "ScenarioId",
    "Unobserved",
    "UnobservedT",
    "age_grid",
    "channels_cache_key",
    "channels_for_preset",
    "guard_joint_memory",
    "is_unobserved",
    "joint_state_count",
    "mask_for",
    "mask_from_channels",
    "preset_for_channels",
    "rich_obs_from_day_log",
    "validate_channels",
]
