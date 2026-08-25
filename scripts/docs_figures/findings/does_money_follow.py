"""Rust-backed: closed-loop profit by observation scenario × seed strip/box plot."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

OUTPUT = "profit-by-scenario-boxplot.png"
# Internal preset ids (unchanged in code); chart uses descriptive labels.
SCENARIOS = ("P0", "P1", "F1", "F2a", "F2")
LABELS = (
    "books only",
    "shrink gun",
    "lot ID at POS",
    "pack date on ASN",
    "lot ID + pack date",
)
SEEDS = tuple(range(1, 9))


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    require_rust_core()
    from blueberries_voi.sim.shipments import smoke_cool_shipments
    from blueberries_voi.voi import run_voi_crn_cell

    target = (out_dir or OUT) / OUTPUT

    by_scenario: dict[str, list[float]] = {s: [] for s in SCENARIOS}
    for seed in SEEDS:
        profit_map = run_voi_crn_cell(
            beta=2.0,
            root_seed=int(seed),
            scenarios=list(SCENARIOS),
            n_burn=2,
            n_score=6,
            filter_n=24,
            H=2,
            n_rollout_paths=0,
            lead_time=1,
            shipments=smoke_cool_shipments(),
        )
        for scenario in SCENARIOS:
            by_scenario[scenario].append(profit_map.get(scenario, float("nan")))

    _fig, ax = plt.subplots(figsize=(9, 4))
    rng = np.random.default_rng(0)
    for i, scenario in enumerate(SCENARIOS):
        pts = np.asarray(by_scenario[scenario], dtype=float)
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
    ax.set_xticks(range(len(SCENARIOS)))
    ax.set_xticklabels(LABELS, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("scored profit")
    ax.set_title("Closed-loop profit — seed variance vs scenario lift")
    save_fig(target)
    return target
