"""Rust-backed: per-unit freshness trajectories for one lot."""

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

OUTPUT = "spoilage-freshness-paths.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    session = EngineSession()
    session.init(
        {
            "shipments": smoke_cool_shipments(),
            "enable_filter": False,
            "L": 3,
            "K": 4,
            "lead_time": 1,
        },
        seed=99,
    )
    session.step(120)

    trajectories: list[list[float]] = []
    for _ in range(40):
        delta = session.step(0)
        lots = delta.get("live_lots") or []
        if not lots:
            continue
        f_values = [float(f) for f in (lots[0].get("f_values") or [])]
        if not f_values:
            continue
        if not trajectories:
            trajectories = [[f] for f in f_values[:15]]
        else:
            for i, f in enumerate(f_values[: len(trajectories)]):
                trajectories[i].append(f)

    _fig, ax = plt.subplots(figsize=(8, 4.5))
    cmap = plt.cm.viridis(np.linspace(0.15, 0.85, max(len(trajectories), 1)))
    for i, traj in enumerate(trajectories):
        ax.plot(range(len(traj)), traj, color=cmap[i], alpha=0.85, lw=1.2)
    ax.axhline(0, color="0.4", ls="--", lw=0.8)
    ax.set_xlabel("day")
    ax.set_ylabel("unit freshness  f")
    ax.set_title("Independent gamma aging — one lot (~15 units)")
    save_fig(target)
    return target
