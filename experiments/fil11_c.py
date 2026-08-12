"""FIL-11 Stage C generative check vs day_step (ADR 0088 / T-012).

Compares production MC LL predictive obs to shared ``day_step`` empiricals at
small L/K. Optionally documents the wrong-physics fail path.
"""

from __future__ import annotations

from pathlib import Path

from blueberries_voi.viz.fil11 import STAGE_C_TV_TOL, run_fil11_stage_c

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "experiments" / "fil11_stage_c_result.md"
FIG = ROOT / "figures" / "m2.5"


def main() -> None:
    c = run_fil11_stage_c(
        figures_dir=FIG,
        L=2,
        K=4,
        n_obs_samples=200,
        tolerance=STAGE_C_TV_TOL,
        inject_wrong_physics=False,
    )
    wrong = run_fil11_stage_c(
        figures_dir=FIG,
        L=2,
        K=4,
        n_obs_samples=200,
        tolerance=STAGE_C_TV_TOL,
        inject_wrong_physics=True,
    )
    status = "PASS" if c.passed else "FAIL"
    print(
        f"Stage C mode={c.mode} divergence={c.divergence:.6f} "
        f"tol={c.tolerance} passed={c.passed}"
    )
    print(f"wrong-physics divergence={wrong.divergence:.6f} passed={wrong.passed}")
    print(f"figure={c.figure_path}")
    NOTE.write_text(
        "# FIL-11 Stage C — generative vs day_step (T-012)\n\n"
        "Production gate is generative agreement with shared `day_step` kernels "
        "(ADR 0088). Soft `tv_vs_exact` is not the gate.\n\n"
        f"- status: **{status}**\n"
        f"- mode: `{c.mode}`\n"
        f"- tolerance (TV on discrete P1 sales/waste): {c.tolerance}\n"
        f"- production divergence: {c.divergence:.6f}\n"
        f"- wrong-physics divergence: {wrong.divergence:.6f} "
        f"(passed={wrong.passed})\n"
        f"- L={c.L}, K={c.K}\n"
        f"- alphabet: empirical support of day_step (sales, waste) pairs\n"
        f"- figure: {c.figure_path}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
