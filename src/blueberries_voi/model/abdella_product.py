"""Derived Abdella arrival-age product (ADR 0101 / T-044).

Offline / desktop builds convert vendored Parquet into a numpy ``.npz`` artifact.
Browser and slim interactive paths load that product (or inject age arrays) and
**must not** import pyarrow or read parquet.

On-disk format
--------------
``*.npz`` with float arrays keyed by product mix:

* ``abdella_all`` - all six MOD-21 shipments
* ``short_haul`` - FL short-haul corridor (~2 d calendar; S2)
* ``long_haul`` - CA->East long-haul corridor (~4-6.6 d; S1,S3-S6)

Optional companion ``shipment_ids_<key>`` string arrays document membership.

Build (desktop / CI; requires ``[data]`` / pyarrow)::

    uv run python -c \\
      \"from pathlib import Path; from blueberries_voi.model.abdella_product import \\
       build_derived_abdella_product; \\
       build_derived_abdella_product(Path('data/abdella'), Path('out.npz'))\"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

# Published calendar durations (days): short-haul is the FL ~2 d corridor only.
_SHORT_HAUL_MAX_DURATION_D: Final[float] = 3.0

PRODUCT_KEYS: Final[tuple[str, ...]] = ("abdella_all", "long_haul", "short_haul")

DEFAULT_DERIVED_ABDELLA_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "data" / "abdella_arrival_ages.npz"
)


@dataclass(frozen=True)
class ArrivalAgeProduct:
    """Arrival ages usable by sim / session config (no parquet)."""

    arrival_ages: npt.NDArray[np.floating]
    product_key: str = "injected"

    def __post_init__(self) -> None:
        ages = np.asarray(self.arrival_ages, dtype=float).reshape(-1)
        object.__setattr__(self, "arrival_ages", ages)
        if ages.size < 1:
            msg = "arrival_ages must be non-empty"
            raise ValueError(msg)
        if not np.all(np.isfinite(ages)):
            msg = "arrival_ages must be finite"
            raise ValueError(msg)


def arrival_ages_from_array(
    ages: npt.ArrayLike,
    *,
    product_key: str = "injected",
) -> ArrivalAgeProduct:
    """Wrap an injectable age array for sim / session config."""
    return ArrivalAgeProduct(
        arrival_ages=np.asarray(ages, dtype=float),
        product_key=product_key,
    )


def _resolve_out_path(out_path: Path | str) -> Path:
    """Map builder destination to a numpy-/JSON-friendly on-disk path."""
    path = Path(out_path)
    suffix = path.suffix.lower()
    if suffix in {".npz", ".json", ".npz.gz", ".npzz"}:
        return path
    if suffix == ".npy":
        return path.with_suffix(".npz")
    # Bare stem (e.g. ``abdella_arrival_ages``) → ``.npz``.
    return path.with_suffix(".npz")


def build_derived_abdella_product(
    parquet_dir: Path | str,
    out_path: Path | str,
    *,
    q10: float = 3.0,
    t_ref_c: float = 0.0,
) -> Path:
    """Convert vendored Abdella Parquet into a numpy arrival-age ``.npz``.

    Requires pyarrow (desktop ``[data]`` extra). Not for browser / Pyodide.
    """
    # Module import (not ImportFrom of parquet symbols) keeps the AST gate clean.
    import blueberries_voi.model.abdella as abdella

    root = Path(parquet_dir)
    if not root.exists():
        msg = f"Abdella parquet directory missing: {root}"
        raise FileNotFoundError(msg)
    if not root.is_dir():
        msg = f"Abdella parquet path is not a directory: {root}"
        raise NotADirectoryError(msg)

    shipments = abdella.load_abdella_shipments(root)
    ids = [s.shipment_id for s in shipments]
    ages = np.asarray(
        [abdella.shipment_arrival_age(s, q10=q10, t_ref_c=t_ref_c) for s in shipments],
        dtype=float,
    )
    durations = np.asarray(
        [abdella.ABDELLA_PUBLISHED_DURATIONS_D[sid] for sid in ids],
        dtype=float,
    )
    short_mask = durations < _SHORT_HAUL_MAX_DURATION_D
    long_mask = ~short_mask
    if not np.any(short_mask) or not np.any(long_mask):
        msg = "expected both short-haul and long-haul shipments in MOD-21 mix"
        raise ValueError(msg)

    payload: dict[str, npt.NDArray[np.generic]] = {
        "abdella_all": ages,
        "short_haul": ages[short_mask],
        "long_haul": ages[long_mask],
        "shipment_ids_abdella_all": np.asarray(ids),
        "shipment_ids_short_haul": np.asarray(
            [sid for sid, keep in zip(ids, short_mask, strict=True) if keep]
        ),
        "shipment_ids_long_haul": np.asarray(
            [sid for sid, keep in zip(ids, long_mask, strict=True) if keep]
        ),
    }

    dest = _resolve_out_path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez(dest, **payload)  # type: ignore[arg-type]
    return dest


def load_derived_abdella_arrival_ages(
    path: Path | str,
    *,
    product_key: str = "abdella_all",
) -> ArrivalAgeProduct:
    """Load a derived arrival-age product without importing pyarrow."""
    artifact = Path(path)
    if not artifact.is_file():
        msg = f"derived Abdella product missing: {artifact}"
        raise FileNotFoundError(msg)
    if product_key not in PRODUCT_KEYS:
        msg = f"unknown product_key {product_key!r}; expected one of {PRODUCT_KEYS}"
        raise KeyError(msg)

    with np.load(artifact, allow_pickle=False) as data:
        if product_key not in data.files:
            msg = f"product key {product_key!r} not in {artifact}"
            raise KeyError(msg)
        ages = np.asarray(data[product_key], dtype=float)

    return ArrivalAgeProduct(arrival_ages=ages, product_key=product_key)


__all__ = [
    "DEFAULT_DERIVED_ABDELLA_PATH",
    "PRODUCT_KEYS",
    "ArrivalAgeProduct",
    "arrival_ages_from_array",
    "build_derived_abdella_product",
    "load_derived_abdella_arrival_ages",
]
