"""Public shipment helpers: production Abdella default vs smoke cool fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from blueberries_voi.model.abdella import ShipmentTrace, load_abdella_shipments

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "default_shipments",
    "ensure_demo_shipments",
    "smoke_cool_shipments",
]


def default_shipments(root: Path | None = None) -> list[ShipmentTrace]:
    """Production default: load Abdella parquet traces (ADR 0104)."""
    return load_abdella_shipments(root)


def smoke_cool_shipments() -> list[ShipmentTrace]:
    """Smoke/test-only synthetic 1C cool traces; not a production default.

    Does not require Abdella parquet on disk.
    """
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
    """Fill missing/empty ``shipments`` with parquet-free smoke fixtures (ADR 0107).

    Host edges (FastAPI / Pyodide RPC) call this before ``EngineSession``;
    non-empty client shipments are left untouched. Does not alter
    ``EngineSession`` itself.
    """
    out = dict(config)
    ships = out.get("shipments")
    if not ships:
        out["shipments"] = smoke_cool_shipments()
    return out
