"""FIL-11 Stage A (then B/C if A passes)."""

from __future__ import annotations

from pathlib import Path

from blueberries_voi.viz.fil11 import (
    run_fil11_stage_a,
    run_fil11_stage_b,
    run_fil11_stage_c,
)

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "experiments" / "fil11_stage_a_result.md"


def main() -> None:
    a = run_fil11_stage_a(figures_dir=ROOT / "figures" / "m1")
    print(
        f"Stage A contracted={a.contracted} "
        f"prior={a.prior_spread:.3f} post={a.posterior_spread:.3f} "
        f"tight={a.tight_posterior_spread:.3f}"
    )
    if not a.contracted:
        NOTE.write_text(
            "# FIL-11 Stage A - FAIL\n\n"
            "Posterior did not contract under full Abdella mix relative to prior "
            "and tight-spread control. Stages B/C stopped per FIL-11=D.\n"
            f"- prior_spread={a.prior_spread:.4f}\n"
            f"- posterior_spread={a.posterior_spread:.4f}\n"
            f"- tight_posterior_spread={a.tight_posterior_spread:.4f}\n"
            f"- figure={a.figure_path}\n",
            encoding="utf-8",
        )
        print("Stage A FAILED - stopping before B/C")
        return

    NOTE.write_text(
        "# FIL-11 Stage A - PASS\n\n"
        f"prior={a.prior_spread:.4f}, posterior={a.posterior_spread:.4f}, "
        f"tight={a.tight_posterior_spread:.4f}\n",
        encoding="utf-8",
    )
    b = run_fil11_stage_b(figures_dir=ROOT / "figures" / "m1", n_reps=50)
    print(f"Stage B coverage={b.coverage_90:.3f} passed={b.passed}")
    c = run_fil11_stage_c(figures_dir=ROOT / "figures" / "m1.5", L=2, K=4)
    print(f"Stage C divergence={c.divergence:.4f} passed={c.passed}")


if __name__ == "__main__":
    main()
