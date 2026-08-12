"""CLI entry for Gate 0 figures."""

from __future__ import annotations

from blueberries_voi.viz.gate0 import run_gate0


def main() -> None:
    g0a, g0b = run_gate0()
    print(
        f"Gate0a var_total={g0a.var_total:.4f} "
        f"duration_share={g0a.duration_share:.3f} "
        f"temp_share={g0a.temperature_share:.3f}"
    )
    print(
        f"Gate0b gap_units={g0b.gap_units:.4f} "
        f"swallowed@8={g0b.swallowed_by_caseround} "
        f"swallowed@4={g0b.gap_cases_case4}"
    )
    print(f"arrival ages={g0a.arrival_ages}")
    print(f"durations={g0a.durations_d}")


if __name__ == "__main__":
    main()
