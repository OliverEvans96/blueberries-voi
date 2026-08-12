"""SIM-05 hierarchical SeedSequence RNG addressed by semantic slot."""

from __future__ import annotations

import hashlib
from typing import Final

import numpy as np

STREAM_DEMAND: Final[str] = ":demand"
STREAM_SPOIL: Final[str] = ":spoil"
STREAM_ALLOC: Final[str] = ":alloc"
STREAM_ARRIVAL_SHIP: Final[str] = ":arrival_ship"
STREAM_ARRIVAL_SENSOR: Final[str] = ":arrival_sensor"
STREAM_FILTER_RESAMPLE: Final[str] = ":filter_resample"

KNOWN_STREAMS: Final[frozenset[str]] = frozenset(
    {
        STREAM_DEMAND,
        STREAM_SPOIL,
        STREAM_ALLOC,
        STREAM_ARRIVAL_SHIP,
        STREAM_ARRIVAL_SENSOR,
        STREAM_FILTER_RESAMPLE,
    }
)


def _stable_u32(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little")


def spawn_rng(
    root_seed: int,
    *,
    run_id: str | int,
    day: int,
    stream: str,
) -> np.random.Generator:
    """Return a Generator addressed by ``(run_id, day, stream)`` under ``root_seed``.

    Streams are independent: consuming draws on one stream does not advance another.
    The same ``(root_seed, run_id, day, stream)`` always yields a bit-identical
    sequence.
    """
    if stream not in KNOWN_STREAMS:
        msg = f"unknown stream {stream!r}; expected one of {sorted(KNOWN_STREAMS)}"
        raise ValueError(msg)
    # Entropy mix is order-stable: spawn tree keyed by semantic slot, not call order.
    entropy = [
        int(root_seed) & 0xFFFFFFFF,
        (int(root_seed) >> 32) & 0xFFFFFFFF,
        _stable_u32(f"run:{run_id}"),
        int(day) & 0xFFFFFFFF,
        _stable_u32(f"stream:{stream}"),
    ]
    ss = np.random.SeedSequence(entropy)
    return np.random.default_rng(ss)
