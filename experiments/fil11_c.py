"""FIL-11 Stage C exact comparison (diagnostic — Stage A already failed).

Oliver requested B/C as diagnostic evidence even though Stage A failed.
This does not reopen the FIL-11=D gate or claim A passed.

Compares full_joint filter vs exact forward at L∈{2,3}, small K; TV tol ~0.05.
"""

from __future__ import annotations

from pathlib import Path

from blueberries_voi.viz.fil11 import STAGE_C_TV_TOL, run_fil11_stage_c

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "experiments" / "fil11_stage_c_result.md"
FIG = ROOT / "figures" / "m1"


def main() -> None:
    c = run_fil11_stage_c(figures_dir=FIG, L=(2, 3), K=4)
    status = "PASS (diagnostic criteria)" if c.passed else "FAIL (diagnostic criteria)"
    tv_lines = "\n".join(f"  - L={li}: TV={c.tvs[li]:.6f}" for li in sorted(c.tvs))
    print(f"Stage C max_tv={c.tv:.6f} tvs={c.tvs} K={c.K} passed={c.passed}")
    print(f"figure={c.figure_path}")
    NOTE.write_text(
        "# FIL-11 Stage C — diagnostic (Stage A FAIL)\n\n"
        "Run at Oliver's request after Stage A contraction failure. "
        "Not a gate reopen; evidence only.\n\n"
        f"- status: **{status}**\n"
        f"- TV tolerance: {STAGE_C_TV_TOL}\n"
        f"- max TV: {c.tv:.6f}\n"
        f"- per-L TVs:\n{tv_lines}\n"
        f"- K: {c.K} (small grid for exact)\n"
        f"- backend: full_joint vs exact forward\n"
        f"- figure: {c.figure_path}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
