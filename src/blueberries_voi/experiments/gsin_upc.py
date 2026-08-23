"""Batch job helpers for ``gsin_upc_diag`` shards."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

N_REGIMES = 4
N_SEEDS = 12
GSIN_SCENARIOS: tuple[str, ...] = ("P0", "P1", "F1", "F2a", "F2", "F3")

REGIME_TITLES: tuple[str, ...] = (
    "Homogeneous fleet, overlapping lots",
    "Heterogeneous fleet, overlapping lots",
    "Heterogeneous fleet, deep shelf",
    "Thermal fleet, overlapping lots",
)

_METRIC_SUM_KEYS = (
    "n",
    "lot_n",
    "count_mae",
    "count_bias",
    "store_meanf_mae",
    "lot_meanf_mae",
    "lot_count_mae",
    "tv_sum",
    "ess_sum",
    "eff_inv_mae",
    "ms",
)


def gsin_seed(seed_index: int) -> int:
    if not 0 <= seed_index < N_SEEDS:
        msg = f"seed_index must be in [0, {N_SEEDS}), got {seed_index}"
        raise ValueError(msg)
    return 90_000 + seed_index * 7


def gsin_job_grid() -> list[tuple[int, int]]:
    """48 independent cells: truth once per (regime, seed), six mask replays."""
    return [
        (regime, seed_idx) for regime in range(N_REGIMES) for seed_idx in range(N_SEEDS)
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def diag_binary() -> Path | None:
    """Locate the release ``gsin_upc_diag`` example binary."""
    env = os.environ.get("GSIN_UPC_DIAG_BIN")
    if env:
        path = Path(env)
        return path if path.is_file() else None
    candidate = _repo_root() / "target" / "release" / "examples" / "gsin_upc_diag"
    return candidate if candidate.is_file() else None


def run_regime_seed(regime_index: int, seed_index: int) -> dict[str, Any]:
    """Run one shard via the Rust example (``--shard``)."""
    if not 0 <= regime_index < N_REGIMES:
        msg = f"regime_index must be in [0, {N_REGIMES}), got {regime_index}"
        raise ValueError(msg)
    binary = diag_binary()
    if binary is None:
        msg = (
            "gsin_upc_diag binary not found; build with:\n"
            "  cargo build -p voi_core --release --example gsin_upc_diag\n"
            "or set GSIN_UPC_DIAG_BIN"
        )
        raise RuntimeError(msg)
    proc = subprocess.run(
        [
            str(binary),
            "--shard",
            str(regime_index),
            str(seed_index),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload: dict[str, Any] = json.loads(proc.stdout)
    return payload


def _aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    agg = {k: 0.0 for k in _METRIC_SUM_KEYS}
    for row in rows:
        metrics = row["metrics"]
        for key in _METRIC_SUM_KEYS:
            agg[key] += float(metrics[key])
    n = max(agg["n"], 1.0)
    ln = max(agg["lot_n"], 1.0)
    return {
        "count_mae": agg["count_mae"] / n,
        "count_bias": agg["count_bias"] / n,
        "store_mean_f_mae": agg["store_meanf_mae"] / n,
        "lot_mean_f_mae": agg["lot_meanf_mae"] / ln,
        "lot_count_mae": agg["lot_count_mae"] / ln,
        "hist_tv": agg["tv_sum"] / n,
        "eff_inv_mae": agg["eff_inv_mae"] / n,
        "ess": agg["ess_sum"] / n,
        "ms_per_day": agg["ms"] / N_SEEDS,
    }


def merge_gsin_diag_rows(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge shard JSON into ``experiments/data/gsin_upc_after.json`` row shape."""
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    series_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for shard in shards:
        regime = str(shard["regime"])
        for entry in shard["channels"]:
            channel = str(entry["channel"])
            key = (regime, channel)
            by_key.setdefault(key, []).append(entry)
            if int(shard.get("seed_index", 0)) == 0:
                series_by_key[key] = dict(entry["series"])
    out: list[dict[str, Any]] = []
    for (regime, channel), entries in sorted(by_key.items()):
        metrics = _aggregate_metrics(entries)
        row: dict[str, Any] = {
            "regime": regime,
            "channel": channel,
            **metrics,
            "series": series_by_key.get((regime, channel), entries[0]["series"]),
        }
        out.append(row)
    return out
