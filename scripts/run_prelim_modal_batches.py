#!/usr/bin/env python3
"""Run notebook 17-18 Modal calculation batches and record wall times."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_wheel_dir = REPO_ROOT / "dist" / "wheel"
_lgtin_bin = REPO_ROOT / "target" / "release" / "examples" / "lgtin_upc_diag"
os.environ.setdefault("BLUEBERRIES_VOI_BACKEND", "rust")
if _wheel_dir.is_dir():
    os.environ["BLUEBERRIES_VOI_WHEEL"] = str(_wheel_dir)
if _lgtin_bin.is_file():
    os.environ["LGTIN_UPC_DIAG_BIN"] = str(_lgtin_bin)

from blueberries_voi.experiments.modal_dispatch import run_batch  # noqa: E402
from blueberries_voi.filter.types import channels_for_preset  # noqa: E402

OUT = REPO_ROOT / "outputs"
BO_JSON = OUT / "sw_alpha_bo.json"
bo_meta: dict = {}
if BO_JSON.is_file():
    bo_meta = json.loads(BO_JSON.read_text(encoding="utf-8"))

PROFIT_PRESET_IDS = ("P0", "P1", "F1", "F2a", "F2", "F3")
PROFIT_CHANNELS = [channels_for_preset(s) for s in PROFIT_PRESET_IDS]
PROFIT_SEEDS = (42, 7, 101, 2024)
N_BURN, N_SCORE = 2, 14
FILTER_DIAG_CELLS = [(r, s) for r in range(4) for s in range(2)]

VAL_SEEDS = (
    tuple(bo_meta.get("val_seeds", (42, 7, 101, 2024))[:4])
    if bo_meta
    else (42, 7, 101, 2024)
)
ALPHA = float(bo_meta.get("best_alpha_profit_soo", 0.9)) if bo_meta else 0.9
RHO = float(bo_meta.get("best_rho_profit_soo", 0.8)) if bo_meta else 0.8
ROLLOUT_H, N_PATHS, RADIUS = 7, 4, 1

BATCHES: list[tuple[str, dict]] = [
    (
        "nb17_lgtin",
        {
            "job": "lgtin",
            "lgtin_cells": FILTER_DIAG_CELLS,
            "out_path": OUT / "nb17_lgtin.json",
        },
    ),
    (
        "nb17_voi_profit",
        {
            "job": "voi_profit",
            "seeds": PROFIT_SEEDS,
            "channels": PROFIT_CHANNELS,
            "include_oracle": True,
            "n_burn": N_BURN,
            "n_score": N_SCORE,
            "n_rollout_paths": 0,
            "out_path": OUT / "nb17_voi_profit.json",
        },
    ),
    (
        "nb18_rollout_eval",
        {
            "job": "rollout_eval",
            "seeds": VAL_SEEDS,
            "arms": ("sw", "rollout"),
            "alphas": (ALPHA,),
            "rho": RHO,
            "n_burn": N_BURN,
            "n_score": N_SCORE,
            "rollout_h": ROLLOUT_H,
            "n_rollout_paths": N_PATHS,
            "candidate_case_radius": RADIUS,
            "out_path": OUT / "nb18_rollout_eval.json",
        },
    ),
]

summary: dict[str, object] = {"batches": []}

for label, kw in BATCHES:
    job = kw.pop("job")
    out_path = kw.get("out_path")
    print(f"\n=== {label} ({job}) ===", flush=True)
    t0 = time.perf_counter()
    rows = run_batch(job, "modal", smoke=False, **kw)
    wall_s = time.perf_counter() - t0
    entry = {
        "label": label,
        "job": job,
        "wall_s": round(wall_s, 2),
        "n_rows": len(rows),
        "out_path": str(out_path) if out_path else None,
    }
    summary["batches"].append(entry)
    print(f"wall={wall_s:.1f}s rows={len(rows)}", flush=True)

timing_path = OUT / "prelim_modal_timing.json"
timing_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(f"\nWrote {timing_path}", flush=True)
