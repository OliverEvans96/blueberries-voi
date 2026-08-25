"""Rust-backed: gamma decrement histograms (cold/warm) + session freshness path."""

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

OUTPUT = "gamma-aging-decrement-and-path.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    core = require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    cold = np.asarray(core.draw_gamma_decrement_samples_py(4000, 4.0, 42), dtype=float)
    warm = np.asarray(core.draw_gamma_decrement_samples_py(4000, 12.0, 43), dtype=float)

    session = EngineSession()
    session.init(
        {"shipments": smoke_cool_shipments(), "enable_filter": False, "L": 2, "K": 4},
        seed=7,
    )
    session.step(96)
    path_f: list[float] = []
    for _ in range(28):
        delta = session.step(0)
        lots = delta.get("live_lots") or []
        if lots:
            mean_f = float(lots[0].get("mean_f", 0.0))
            if mean_f > 0:
                path_f.append(mean_f)
        elif path_f:
            break

    _fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    bins = np.linspace(0, max(0.25, cold.max(), warm.max()), 30)
    axes[0].hist(cold, bins=bins, alpha=0.65, label="4 °C store", color="#2563eb")
    axes[0].hist(warm, bins=bins, alpha=0.55, label="12 °C store", color="#dd8452")
    axes[0].set_xlabel("daily decrement  Δ")
    axes[0].set_ylabel("count")
    axes[0].set_title("draw_gamma_decrement_samples_py")
    axes[0].legend(frameon=False)

    if path_f:
        axes[1].plot(range(len(path_f)), path_f, "-", color="#2ca02c", lw=2)
    axes[1].axhline(0, color="0.5", ls="--", lw=0.8)
    axes[1].set_xlabel("day")
    axes[1].set_ylabel("mean live freshness  f")
    axes[1].set_title("EngineSession path after delivery")

    save_fig(target)
    return target
