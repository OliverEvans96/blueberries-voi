"""Rust-backed: closed-loop profit by rung × seed strip/box plot."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

OUTPUT = "profit-by-rung-boxplot.png"
RUNGS = ("P0", "P1", "F1", "F2a", "F2")
SEEDS = tuple(range(1, 9))


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    require_rust_core()
    from blueberries_voi.sim.shipments import smoke_cool_shipments
    from blueberries_voi.voi import run_voi_crn_cell

    target = (out_dir or OUT) / OUTPUT

    by_rung: dict[str, list[float]] = {r: [] for r in RUNGS}
    for seed in SEEDS:
        profit_map = run_voi_crn_cell(
            beta=2.0,
            root_seed=int(seed),
            scenarios=list(RUNGS),
            n_burn=2,
            n_score=6,
            filter_n=24,
            H=2,
            n_rollout_paths=0,
            lead_time=1,
            shipments=smoke_cool_shipments(),
        )
        for rung in RUNGS:
            by_rung[rung].append(profit_map.get(rung, float("nan")))

    _fig, ax = plt.subplots(figsize=(8, 4))
    rng = np.random.default_rng(0)
    for i, rung in enumerate(RUNGS):
        pts = np.asarray(by_rung[rung], dtype=float)
        ax.boxplot(
            pts,
            positions=[i],
            widths=0.35,
            patch_artist=True,
            boxprops={"facecolor": "#2563eb", "alpha": 0.25},
            medianprops={"color": "#c44e52"},
        )
        jitter = rng.uniform(-0.12, 0.12, size=len(pts))
        ax.scatter(i + jitter, pts, s=14, color="#2563eb", alpha=0.65, zorder=3)
    ax.set_xticks(range(len(RUNGS)))
    ax.set_xticklabels(RUNGS)
    ax.set_ylabel("scored profit")
    ax.set_title("run_voi_crn_cell_py — seed variance vs rung lift")
    save_fig(target)
    return target
