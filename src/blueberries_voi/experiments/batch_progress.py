"""Lightweight timestamped progress lines for Modal / local batch drivers."""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime
from typing import Any


def ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_line(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)
    sys.stdout.flush()


def channel_key(channel: dict[str, Any]) -> str:
    waste = "1" if channel.get("scan_waste") else "0"
    return (
        f"code={channel.get('code_type')}|waste={waste}|"
        f"hist={channel.get('delivery_history')}"
    )


def log_nb13_start(
    seed: int,
    channel: dict[str, Any],
    *,
    job_index: int | None = None,
) -> float:
    pid = os.getpid()
    idx = f" job={job_index}" if job_index is not None else ""
    log_line(f"nb13 start seed={seed} channel={channel_key(channel)} pid={pid}{idx}")
    return time.perf_counter()


def log_nb13_done(
    seed: int,
    channel: dict[str, Any],
    t0: float,
    *,
    job_index: int | None = None,
) -> float:
    elapsed = time.perf_counter() - t0
    pid = os.getpid()
    idx = f" job={job_index}" if job_index is not None else ""
    log_line(
        f"nb13 done seed={seed} channel={channel_key(channel)} "
        f"elapsed_s={elapsed:.1f} pid={pid}{idx}"
    )
    return elapsed


def log_grid_progress(completed: int, total: int, *, label: str = "nb13") -> None:
    log_line(f"{label} grid: {completed}/{total} complete")
