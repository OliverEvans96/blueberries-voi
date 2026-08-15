"""FIL-11 Stage B calibration (diagnostic — Stage A already failed).

Oliver requested B/C as diagnostic evidence even though Stage A failed.
This does not reopen the FIL-11=D gate or claim A passed.

Production settings: full_joint particle filter, K=8, N=2000, shared day_step.
"""

from __future__ import annotations

from pathlib import Path

from blueberries_voi.filter.constants import PRODUCTION_K, PRODUCTION_N
from blueberries_voi.viz.fil11 import run_fil11_stage_b

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "experiments" / "fil11_stage_b_result.md"
FIG = ROOT / "figures" / "m1"


def main() -> None:
    b = run_fil11_stage_b(
        figures_dir=FIG,
        n_reps=50,
        n_particles=PRODUCTION_N,
        K=PRODUCTION_K,
    )
    status = "PASS (diagnostic criteria)" if b.passed else "FAIL (diagnostic criteria)"
    print(
        f"Stage B coverage_90={b.coverage_90:.3f} "
        f"rank_mean={b.rank_mean:.3f} rank_std={b.rank_std:.3f} "
        f"N={b.n_particles} K={b.K} R={b.n_reps} passed={b.passed}"
    )
    print(f"figure={b.figure_path}")
    NOTE.write_text(
        "# FIL-11 Stage B — diagnostic (Stage A FAIL)\n\n"
        "Run at Oliver's request after Stage A contraction failure. "
        "Not a gate reopen; evidence only.\n\n"
        f"- status: **{status}**\n"
        f"- coverage_90: {b.coverage_90:.4f} (band [0.70, 0.99] around nominal 90%)\n"
        f"- rank_mean: {b.rank_mean:.4f}\n"
        f"- rank_std: {b.rank_std:.4f}\n"
        f"- n_reps: {b.n_reps}\n"
        f"- N (particles): {b.n_particles}\n"
        f"- K: {b.K}\n"
        f"- backend: full_joint (production)\n"
        f"- figure: {b.figure_path}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
