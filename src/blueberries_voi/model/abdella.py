"""Abdella cold-chain shipment traces (MOD-21 / X-08)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from blueberries_voi.model import q10_age_increment

SENSOR_COLUMNS: tuple[str, ...] = (
    "Front_Top",
    "Front_Middle",
    "Front_Bottom",
    "Middle_Top",
    "Middle_Middle",
    "Middle_Bottom",
    "Rear_Top",
    "Rear_Middle",
    "Rear_Bottom",
)

# Abdella et al. 2021 Table 2: harvest → end of instrumented chain (days).
# HF release spans are longer; we clip to these published windows (see PROVENANCE).
ABDELLA_PUBLISHED_DURATIONS_D: dict[str, float] = {
    "S1": 6.0 + 9.0 / 24.0 + 28.0 / 1440.0,
    "S2": 2.0 + 1.0 / 24.0 + 9.0 / 1440.0,
    "S3": 6.0 + 9.0 / 24.0 + 25.0 / 1440.0,
    "S4": 5.0 + 12.0 / 24.0 + 5.0 / 1440.0,
    "S5": 6.0 + 14.0 / 24.0 + 53.0 / 1440.0,
    "S6": 4.0 + 4.0 / 24.0 + 35.0 / 1440.0,
}


@dataclass(frozen=True)
class ShipmentTrace:
    """One Abdella shipment temperature path (lot-average of sensors)."""

    shipment_id: str
    times_d: np.ndarray  # days from harvest start
    temps_c: np.ndarray  # °C, lot-average across available sensors
    duration_d: float


def default_abdella_root() -> Path:
    """Repo-relative ``data/abdella`` when running from a checkout."""
    return Path(__file__).resolve().parents[3] / "data" / "abdella"


def _parse_time(value: str) -> datetime:
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    msg = f"unrecognised Abdella timestamp: {value!r}"
    raise ValueError(msg)


def _lot_mean_temps(table: pq.Table) -> np.ndarray:
    mats: list[np.ndarray] = []
    for col in SENSOR_COLUMNS:
        if col not in table.column_names:
            continue
        mats.append(np.asarray(table.column(col).to_pylist(), dtype=float))
    if not mats:
        msg = "no sensor columns found in Abdella parquet"
        raise ValueError(msg)
    stacked = np.vstack(mats)
    finite = np.isfinite(stacked)
    counts = finite.sum(axis=0)
    summed = np.where(finite, stacked, 0.0).sum(axis=0)
    mean = np.full(stacked.shape[1], np.nan, dtype=float)
    np.divide(summed, counts, out=mean, where=counts > 0)
    return mean


def load_abdella_shipments(root: Path | None = None) -> list[ShipmentTrace]:
    """Load all six shipment traces; raise if any file is missing.

    Does not invent synthetic temperature paths as a fallback.
    """
    base = default_abdella_root() if root is None else Path(root)
    if not base.is_dir():
        msg = (
            f"Abdella data directory missing: {base}. "
            "Populate data/abdella/ from Hugging Face "
            "(NifferLi/cold-chain-strawberry-sensors) - do not invent traces."
        )
        raise FileNotFoundError(msg)

    shipments: list[ShipmentTrace] = []
    for idx in range(1, 7):
        sid = f"S{idx}"
        path = base / f"s{idx}.parquet"
        if not path.is_file():
            msg = (
                f"Missing Abdella shipment file {path}. "
                "Stop and restore vendored parquet - no synthetic T-paths."
            )
            raise FileNotFoundError(msg)
        table = pq.read_table(path)
        raw_times = [_parse_time(str(x)) for x in table.column("Time").to_pylist()]
        t0 = raw_times[0]
        times_d = np.asarray(
            [(t - t0).total_seconds() / 86400.0 for t in raw_times],
            dtype=float,
        )
        temps = _lot_mean_temps(table)
        published = ABDELLA_PUBLISHED_DURATIONS_D[sid]
        mask = times_d <= published + 1e-9
        if int(mask.sum()) < 2:
            msg = f"shipment {sid}: fewer than 2 samples within published duration"
            raise ValueError(msg)
        times_c = times_d[mask]
        temps_c = temps[mask]
        # Drop leading/trailing all-nan; interpolate small gaps.
        valid = np.isfinite(temps_c)
        if not np.any(valid):
            msg = f"shipment {sid}: no finite temperatures in published window"
            raise ValueError(msg)
        # Forward/back fill nan for integration stability.
        filled = temps_c.copy()
        idx_valid = np.where(valid)[0]
        filled[: idx_valid[0]] = filled[idx_valid[0]]
        for i in range(1, len(filled)):
            if not np.isfinite(filled[i]):
                filled[i] = filled[i - 1]
        # Start at first cool-chain sample (T<10°C). Warm harvest spikes before
        # precool dominate Arrhenius age and push τ ≫ calendar duration; MOD-21 /
        # FIL-15 grid [0,8] assumes the refrigerated leg (see PROVENANCE).
        cool = np.where(filled < 10.0)[0]
        if len(cool) >= 2:
            i0 = int(cool[0])
            times_c = times_c[i0:]
            filled = filled[i0:]
        duration = float(times_c[-1] - times_c[0])
        shipments.append(
            ShipmentTrace(
                shipment_id=sid,
                times_d=times_c - times_c[0],
                temps_c=filled,
                duration_d=duration,
            )
        )
    return shipments


def arrival_age_from_path(
    temps_c: np.ndarray,
    times_d: np.ndarray,
    *,
    q10: float = 3.0,
    t_ref_c: float = 0.0,
) -> float:
    """Integrate Q10/Arrhenius acceleration along a temperature path."""
    if len(temps_c) != len(times_d) or len(times_d) < 2:
        msg = "temps_c and times_d must be same length >= 2"
        raise ValueError(msg)
    age = 0.0
    for i in range(len(times_d) - 1):
        dt = float(times_d[i + 1] - times_d[i])
        if dt <= 0.0:
            continue
        t_mid = 0.5 * (float(temps_c[i]) + float(temps_c[i + 1]))
        age += q10_age_increment(dt, t_store_c=t_mid, t_ref_c=t_ref_c, q10=q10)
    return float(age)


def shipment_arrival_age(
    shipment: ShipmentTrace,
    *,
    q10: float = 3.0,
    t_ref_c: float = 0.0,
) -> float:
    return arrival_age_from_path(
        shipment.temps_c,
        shipment.times_d,
        q10=q10,
        t_ref_c=t_ref_c,
    )
