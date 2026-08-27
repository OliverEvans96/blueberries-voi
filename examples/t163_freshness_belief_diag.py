#!/usr/bin/env python3
"""T-163 freshness + belief calibration diagnostic (<10 min).

Runs the Rust MC examples and prints reference metrics.
Execute from repo root:

    uv run python examples/t163_freshness_belief_diag.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main() -> None:
    print("=== T-163 freshness / belief diagnostic ===\n")
    print("Direct multilot draw + filter Prior (t163_f_diag):")
    print(
        run(
            [
                "cargo",
                "run",
                "-p",
                "voi_core",
                "--release",
                "--example",
                "t163_f_diag",
            ]
        )
    )
    print("Session multilot arrival (t163_session_f_diag):")
    print(
        run(
            [
                "cargo",
                "run",
                "-p",
                "voi_core",
                "--release",
                "--example",
                "t163_session_f_diag",
            ]
        )
    )
    print("Ladder MAE fixture (ladder_sweep):")
    print(
        run(
            [
                "cargo",
                "run",
                "-p",
                "voi_core",
                "--release",
                "--example",
                "ladder_sweep",
            ]
        )
    )
    print(
        "\nPre-calibration (integrate @ reference_life_days=14, "
        "sync_params overwrite): arrival f often below 0.5; session truth looked "
        "biased vs Prior when only one multilot segment was aggregated across the "
        "full delivery quantity."
    )


if __name__ == "__main__":
    sys.exit(main())
