"""Rust-backed: raw unit counts vs E[f]-weighted effective inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT
from _style import apply_doc_style, save_fig

from blueberries_voi.filter.belief import ShelfBelief, effective_inventory

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "effective-inventory-raw-vs-weighted.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    target = (out_dir or OUT) / OUTPUT

    f_grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    belief = ShelfBelief(
        lot_counts=[10.0, 8.0, 6.0, 4.0],
        f_marginals=[
            [0.05, 0.15, 0.3, 0.3, 0.2],
            [0.1, 0.2, 0.35, 0.25, 0.1],
            [0.15, 0.25, 0.3, 0.2, 0.1],
            [0.2, 0.3, 0.25, 0.15, 0.1],
        ],
        f_grid=f_grid,
    )
    raw = np.asarray(belief.lot_counts, dtype=float)
    weighted = np.asarray(
        [
            float(n) * sum(p * f for p, f in zip(row, f_grid, strict=True))
            for n, row in zip(belief.lot_counts, belief.f_marginals, strict=True)
        ],
        dtype=float,
    )
    eff_total = effective_inventory(belief, pending_orders={8: 1})

    lots = [f"Lot {i + 1}" for i in range(len(raw))]
    x = np.arange(len(lots))
    width = 0.35
    _fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - width / 2, raw, width, label="raw count", color="#8c8c8c")
    ax.bar(x + width / 2, weighted, width, label="× E[f|lot]", color="#2563eb")
    ax.axhline(eff_total - 8.0, color="#2ca02c", ls=":", lw=1.2, label="on-hand Ĩ")
    ax.axhline(eff_total, color="#c44e52", ls="--", lw=1.2, label="Ĩ + pipeline")
    ax.set_xticks(x)
    ax.set_xticklabels(lots)
    ax.set_ylabel("units")
    ax.set_title("Skewed lots: raw counts vs effective_inventory")
    ax.legend(frameon=False, fontsize=8)
    save_fig(target)
    return target
