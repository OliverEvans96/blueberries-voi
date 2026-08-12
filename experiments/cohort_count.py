"""Cohort-count figure for T-004."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    ep = run_episode(
        ModelParams(),
        root_seed=5,
        run_id="cohorts",
        n_burn=30,
        n_score=90,
        shipments=ships,
    )
    Ls = [d.L for d in ep.days]
    out = ROOT / "figures" / "m1"
    out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(Ls, color="#264653", lw=1.2)
    ax.axvline(ep.n_burn, color="gray", ls="--", label="end burn-in")
    ax.set_xlabel("Day")
    ax.set_ylabel("Live cohort count L")
    scored = Ls[ep.n_burn :]
    ax.set_title(
        f"Cohort count (M1 open-loop S=60) - "
        f"p50={np.percentile(scored, 50):.0f} "
        f"p90={np.percentile(scored, 90):.0f} "
        f"max={np.max(scored)}"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "cohort_count.png", dpi=120)
    plt.close(fig)
    print("Wrote", out / "cohort_count.png")


if __name__ == "__main__":
    main()
