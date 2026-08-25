"""Rust-backed: picking weight vs freshness for σ=0 vs σ=0.5."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "picking-weight-freshness.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    core = require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    f_vals = np.linspace(0.1, 1.0, 10)
    w_uniform = np.asarray(
        core.picking_weights_f_py(list(f_vals), 0.5, True), dtype=float
    )
    w_sigma = np.asarray(
        core.picking_weights_f_py(list(f_vals), 0.5, False), dtype=float
    )

    _fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.035
    ax.bar(
        f_vals - width,
        w_uniform,
        width=width,
        label="σ=0 (uniform_picking)",
        color="#8c8c8c",
    )
    ax.bar(
        f_vals + width,
        w_sigma,
        width=width,
        label="σ=0.5",
        color="#2563eb",
    )
    ax.set_xlabel("freshness  f")
    ax.set_ylabel("normalized pick weight")
    ax.set_title("Picking weights from Rust picking_weights_f")
    ax.legend(frameon=False)
    save_fig(target)
    return target
