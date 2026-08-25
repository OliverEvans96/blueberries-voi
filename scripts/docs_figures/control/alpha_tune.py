"""Rust-backed: alpha-tune profit curve over DEFAULT_DESKTOP_ALPHAS."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from _paths import OUT
from _rust import require_rust_core
from _style import apply_doc_style, save_fig

from blueberries_voi.sim.alpha_tune import DEFAULT_DESKTOP_ALPHAS

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = "alpha-tune-profit-curve.png"


def render(out_dir: Path | None = None) -> Path:
    apply_doc_style()
    core = require_rust_core()
    target = (out_dir or OUT) / OUTPUT

    profits: list[float] = []
    for alpha in DEFAULT_DESKTOP_ALPHAS:
        profit, _, _ = core.evaluate_alpha_tune_outcomes_py(
            "sw",
            float(alpha),
            42,
            n_burn=2,
            n_score=8,
        )
        profits.append(float(profit))

    _fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(
        list(DEFAULT_DESKTOP_ALPHAS),
        profits,
        "o-",
        color="#2563eb",
        label="damped SW scored profit",
    )
    best_i = max(range(len(profits)), key=lambda i: profits[i])
    ax.scatter(
        [DEFAULT_DESKTOP_ALPHAS[best_i]],
        [profits[best_i]],
        s=80,
        color="#c44e52",
        zorder=5,
        label=f"max @ α={DEFAULT_DESKTOP_ALPHAS[best_i]}",
    )
    ax.set_xlabel("service level  α")
    ax.set_ylabel("scored episode profit")
    ax.set_title("evaluate_alpha_tune_outcomes_py — desktop α grid")
    ax.legend(frameon=False)
    save_fig(target)
    return target
