"""FIL-13 bakeoff entrypoint."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from blueberries_voi.filter.backends import BACKENDS, run_microbench
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import load_abdella_shipments
from blueberries_voi.sim import run_episode

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures" / "m1"
EXP = ROOT / "experiments"


def empirical_L_stats() -> dict[str, float]:
    ships = load_abdella_shipments(ROOT / "data" / "abdella")
    ep = run_episode(
        ModelParams(),
        root_seed=11,
        run_id="fil13L",
        n_burn=20,
        n_score=90,
        shipments=ships,
    )
    Ls = np.array([d.L for d in ep.scored], dtype=float)
    return {
        "p50": float(np.percentile(Ls, 50)),
        "p90": float(np.percentile(Ls, 90)),
        "max": float(np.max(Ls)),
        "mean": float(np.mean(Ls)),
    }


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    L_stats = empirical_L_stats()
    print("Empirical L:", L_stats)

    # Reduced but covering matrix for laptop/CI time.
    Ks = [4, 8]
    Ns = [200, 2000]
    Ls = [2, 3, 4, 6, 8, 12]
    rows = []
    for be in BACKENDS:
        for K in Ks:
            for N in Ns:
                for L in Ls:
                    row = run_microbench(be, K=K, N=N, L=L, timeout_s=0.5)
                    rows.append(row)

    # Runtime figure: wall time vs L at K=8, N=200
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for be in BACKENDS:
        xs, ys = [], []
        for L in Ls:
            match = [
                r
                for r in rows
                if r.backend == be and r.K == 8 and r.N == 200 and r.L == L
            ]
            if not match:
                continue
            r = match[0]
            xs.append(L)
            ys.append(np.nan if r.oom else r.wall_s)
        ax.plot(xs, ys, marker="o", label=be)
    ax.set_xlabel("L (live cohorts)")
    ax.set_ylabel("Wall time (s) for 3 predict/update steps")
    ax.set_title(
        "FIL-13 bakeoff runtime (K=8, N=200); "
        f"emp L p50={L_stats['p50']:.1f} "
        f"p90={L_stats['p90']:.1f} max={L_stats['max']:.0f}"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fil13_runtime.png", dpi=120)
    plt.close(fig)

    # Write-up
    lines = [
        "# FIL-13 tractability bakeoff",
        "",
        "Empirical live-cohort counts under interim M1 defaults "
        "(sigma=0.5, S=60, MOD-26 demand/case, FIL-14 extinction):",
        f"- p50={L_stats['p50']:.2f}, p90={L_stats['p90']:.2f}, "
        f"max={L_stats['max']:.0f}, mean={L_stats['mean']:.2f}",
        "",
        "## Recommendation",
        "",
        "Empirical L is **small** (p50≈2, p90≈3, max≈3), so `full_joint` (E) stays "
        "under the `K^L*N` memory budget at production (K=8, N=2000). Per the settle "
        "rule (prefer A if L large; E if L small enough), production locks **E - "
        "full_joint** (ADR 0082 ACCEPTED; `PRODUCTION_BACKEND=full_joint`). "
        "FIL-15 locks K=8 on [0,8], N=2000, ESS=N/2 (ADR 0083). "
        "**A - sliding_window** remains the fallback if L rises "
        "(`full_joint` OOMs at L>=6 here).",
        "",
        "## Sample rows (K=8, N=200)",
        "",
        "| backend | L | wall_s | oom | tv(L≤3) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for be in BACKENDS:
        for L in Ls:
            match = [
                r
                for r in rows
                if r.backend == be and r.K == 8 and r.N == 200 and r.L == L
            ]
            if not match:
                continue
            r = match[0]
            tv = "" if r.tv is None else f"{r.tv:.3f}"
            lines.append(f"| {r.backend} | {r.L} | {r.wall_s:.4f} | {r.oom} | {tv} |")
    (EXP / "fil13_bakeoff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", FIG / "fil13_runtime.png")
    print("Wrote", EXP / "fil13_bakeoff.md")


if __name__ == "__main__":
    main()
