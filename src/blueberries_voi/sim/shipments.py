"""Public shipment helpers: parametric MOD-21 demo vs smoke cool fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.model.abdella import ShipmentTrace

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "default_shipments",
    "ensure_demo_shipments",
    "mod21_demo_shipments",
    "smoke_cool_shipments",
]

# MOD-21 demo durations at 1 °C (crates/voi_core/src/shipments.rs).
_MOD21_DEMO_DURATIONS_D: tuple[float, ...] = (
    5.434,
    2.194,
    7.582,
    6.865,
    7.504,
    5.405,
)


def _mod21_demo_trace(duration_d: float) -> ShipmentTrace:
    return ShipmentTrace(
        shipment_id="MOD21-DEMO",
        times_d=np.asarray([0.0, duration_d], dtype=float),
        temps_c=np.asarray([1.0, 1.0], dtype=float),
        duration_d=float(duration_d),
    )


def mod21_demo_shipments(product: str = "abdella_all") -> list[ShipmentTrace]:
    """Parquet-free MOD-21 demo traces (constant 1 °C; durations from fit epoch)."""
    durs = _MOD21_DEMO_DURATIONS_D
    if product == "short_haul":
        return [_mod21_demo_trace(durs[1])]
    if product == "long_haul":
        return [_mod21_demo_trace(d) for i, d in enumerate(durs) if i != 1]
    return [_mod21_demo_trace(d) for d in durs]


def default_shipments(root: Path | None = None) -> list[ShipmentTrace]:
    """Production default: fitted MOD-21 mix without parquet (ADR 0148)."""
    del root
    return mod21_demo_shipments("abdella_all")


def smoke_cool_shipments() -> list[ShipmentTrace]:
    """Smoke/test-only synthetic 1C cool traces; not a production default."""
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="SMOKE-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def ensure_demo_shipments(config: dict[str, Any]) -> dict[str, Any]:
    """Fill missing/empty ``shipments`` with parquet-free smoke fixtures (ADR 0107)."""
    out = dict(config)
    ships = out.get("shipments")
    if not ships:
        out["shipments"] = smoke_cool_shipments()
    return out
