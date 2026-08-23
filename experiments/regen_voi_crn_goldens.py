#!/usr/bin/env python3
"""Regenerate VOI CRN golden fixtures and patch test_t139 baseline."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from blueberries_voi.backend import rust_available
from blueberries_voi.voi import VOI_SCENARIOS, run_voi_crn_cell

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "voi_crn"
TEST_T139 = ROOT / "tests" / "test_t139_voi_crn_sd0.py"
PHYSICS_EPOCH = "t150-f-native-arrival"

BUDGETS = {
    "beta": 2.0,
    "n_burn": 2,
    "n_score": 8,
    "filter_n": 32,
    "H": 2,
    "n_rollout_paths": 2,
    "lead_time": 1,
}
SEEDS = (1, 42)


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "unknown"


def _run_cell(root_seed: int) -> dict[str, float]:
    return run_voi_crn_cell(
        root_seed=root_seed,
        scenarios=list(VOI_SCENARIOS),
        **BUDGETS,
    )


def _patch_test_t139(primary: dict[str, float]) -> None:
    lines = ["_T150_BASELINE: dict[str, float] = {"]
    for name in VOI_SCENARIOS:
        lines.append(f'    "{name}": {primary[name]:.1f},')
    block = "\n".join(lines) + "\n}\n"
    text = TEST_T139.read_text(encoding="utf-8")
    new_text, n = re.subn(
        r"# T-141 implement tip.*?\n_T141_BASELINE: dict\[str, float\] = \{.*?\n\}\n",
        f"# T-150 f-native arrival physics ({PHYSICS_EPOCH}).\n{block}",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n != 1:
        raise RuntimeError("could not patch test_t139 baseline block")
    new_text = new_text.replace("_T141_BASELINE[scenario]", "_T150_BASELINE[scenario]")
    TEST_T139.write_text(new_text, encoding="utf-8")


def main() -> None:
    if not rust_available():
        print("error: build _core first", file=sys.stderr)
        sys.exit(1)

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    primary: dict[str, float] | None = None
    for seed in SEEDS:
        profits = _run_cell(seed)
        path = FIXTURE_DIR / f"seed{seed}_abdella.json"
        payload = {
            "physics_epoch": PHYSICS_EPOCH,
            "generated_from_commit": _git_head(),
            "alpha_note": (
                "run_voi_crn_cell smoke default alpha=0.9; "
                "tuned_alpha.json optional (see regen_tuned_alpha.py)"
            ),
            "budgets": {**BUDGETS, "root_seed": seed, "shipments": "default_shipments"},
            "profits": {k: round(float(profits[k]), 6) for k in VOI_SCENARIOS},
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        summary = "  ".join(f"{n}={profits[n]:.1f}" for n in VOI_SCENARIOS)
        print(f"seed {seed}: {summary}")
        if seed == 1:
            primary = profits

    assert primary is not None
    _patch_test_t139(primary)
    print(f"patched {TEST_T139.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
