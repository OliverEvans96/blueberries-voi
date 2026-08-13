"""ENG-03 static VOI-vs-β figure hook (matplotlib lives here, not in ``voi/``)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueberries_voi.voi.sweep import VoISweepResult

__all__ = [
    "plot_voi_vs_beta",
]


def plot_voi_vs_beta(
    result: VoISweepResult,
    *,
    out_path: Path | str,
    use_pct: bool = True,
) -> Path:
    """Write a static matplotlib PNG of VOI vs β per scenario."""
    # Import inside the function so ``voi`` core never pulls matplotlib.
    import matplotlib.pyplot as plt

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    by_scen: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    for arm in result.arms:
        y = float(arm.pct_vs_p0) if use_pct else float(arm.absolute_delta)
        by_scen[arm.scenario].append(
            (float(arm.beta), y, float(arm.ci_low), float(arm.ci_high))
        )

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    for scen, rows in sorted(by_scen.items()):
        rows_sorted = sorted(rows, key=lambda t: t[0])
        xs = [r[0] for r in rows_sorted]
        ys = [r[1] for r in rows_sorted]
        ax.plot(xs, ys, marker="o", label=scen)
    ax.axhline(0.0, color="0.5", linewidth=0.8)
    ax.set_xlabel("β")
    ax.set_ylabel("% vs P0" if use_pct else "Absolute Δ$ vs P0")
    title = "VOI vs β (smoke)" if result.smoke else "VOI vs β"
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
