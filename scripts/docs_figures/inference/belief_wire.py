"""Rust-backed: belief wire histogram vs unit-level freshness scatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

from blueberries_voi.sim.shipments import smoke_cool_shipments
from blueberries_voi.simulator.session import EngineSession

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "belief-wire-histogram.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    session = EngineSession()
    session.init(
        {
            "shipments": smoke_cool_shipments(),
            "obs_scenario": "F1",
            "L": 4,
            "K": 8,
            "n_particles": 64,
        },
        seed=17,
    )
    delta = None
    for _ in range(12):
        delta = session.step(48)
        belief = delta["belief"]
        if any(float(x) > 0 for x in belief["lot_counts"]):
            break
    assert delta is not None
    belief = delta["belief"]
    f_grid = [float(x) for x in belief["f_grid"]]
    l_dim = int(belief["L"])
    k_dim = int(belief["K"])
    marginals = np.asarray(belief["f_marginals"], dtype=float).reshape(l_dim, k_dim)
    lot_counts = [float(x) for x in belief["lot_counts"]]

    live_lots = delta.get("live_lots") or []
    unit_pts: list[tuple[float, float]] = []
    for row_idx, lot in enumerate(live_lots[:l_dim]):
        y = l_dim - row_idx
        for f in lot.get("f_values") or []:
            unit_pts.append((float(f), float(y)))

    _fig, axes = plt.subplots(
        1, 2, figsize=(9, 5), gridspec_kw={"width_ratios": [3, 1]}
    )
    ax_hist, ax_dots = axes

    for row_idx in range(l_dim):
        if lot_counts[row_idx] <= 0:
            continue
        y = l_dim - row_idx
        row = marginals[row_idx]
        left = 0.0
        for prob, _f_center in zip(row, f_grid, strict=True):
            if prob <= 0:
                continue
            ax_hist.barh(
                y,
                prob,
                left=left,
                height=0.55,
                color="#2563eb",
                alpha=min(1.0, 0.35 + prob * 2),
                edgecolor="none",
            )
            left += prob

    if unit_pts:
        xs, ys = zip(*unit_pts, strict=True)
        ax_dots.scatter(xs, ys, s=10, color="#c44e52", alpha=0.75)
    ax_dots.set_xlim(-0.02, 1.02)
    ax_dots.set_ylim(0.5, l_dim + 0.5)
    ax_dots.set_title("unit f", fontsize=9)
    ax_dots.set_yticks([])

    ax_hist.set_xlabel("freshness bin mass")
    ax_hist.set_ylabel("lot slot (oldest top)")
    ax_hist.set_title("f_marginals wire")
    save_fig(target)
    return target
