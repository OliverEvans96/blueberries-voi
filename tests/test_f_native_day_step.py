"""AC-daystep physics fixtures and f-native day_step contract (T-C2-A qa-daystep)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DAY_STEP_SRC = REPO_ROOT / "crates" / "voi_core" / "src" / "day_step.rs"
PHYSICS_SRC = REPO_ROOT / "crates" / "voi_core" / "src" / "physics.rs"


def _cargo_test_profile() -> tuple[str, ...]:
    """CI prebuilds release test binaries; dev profile would recompile voi_*."""
    profile: tuple[str, ...] = ("--locked",)
    if os.environ.get("CI", "").lower() == "true":
        profile = ("--release", *profile)
    return profile


def _production_src(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("#[cfg(test)]")[0]


def _require_f_native_day_step_api() -> None:
    src = _production_src(DAY_STEP_SRC)
    assert "pub struct UnitDayStepIn" in src, "RED: UnitDayStepIn not implemented"
    assert "pub struct UnitDayStepOut" in src, "RED: UnitDayStepOut not implemented"
    assert "pub fn unit_day_step" in src, "RED: unit_day_step not implemented"
    assert "death_prob_survival_ratio" not in src, (
        "RED: production day_step must not use Weibull spoil"
    )
    assert "q10_age_increment" not in src, (
        "RED: production day_step must not bump tau via q10_age_increment"
    )


def _require_picking_weights_f() -> None:
    src = _production_src(PHYSICS_SRC)
    assert "pub fn picking_weights_f" in src, "RED: picking_weights_f not implemented"


def ref_picking_weights_f(
    freshness: list[float], *, sigma: float, uniform: bool
) -> list[float]:
    if uniform or sigma <= 0.0 or not freshness:
        n = len(freshness)
        return [1.0 / n] * n
    raw = [max(f, 0.0) ** sigma for f in freshness]
    total = sum(raw)
    return [w / total for w in raw]


def alive_by_lot(freshness: list[float], lot_offsets: list[int]) -> list[int]:
    return [
        sum(
            1
            for f in freshness[lot_offsets[lot_idx] : lot_offsets[lot_idx + 1]]
            if f > 0.0
        )
        for lot_idx in range(len(lot_offsets) - 1)
    ]


@pytest.fixture
def f_native_scripted_grid() -> dict[str, Any]:
    """L=2, U=15 virtual grid for conservation checks."""
    units_per_lot = 15
    lots = 2
    return {
        "freshness": [0.85] * (units_per_lot * lots),
        "lot_offsets": [i * units_per_lot for i in range(lots + 1)],
        "units_per_lot": units_per_lot,
        "gamma_decrement": 0.05,
        "demand": 5,
    }


@pytest.fixture
def f_native_delivery_prior() -> dict[str, Any]:
    return {
        "units_per_lot": 15,
        "lot_offsets": [0, 15],
        "delivery_lot": 0,
        "delivery_f": 0.92,
    }


def test_day_step_f_native_exports_unit_day_step_api() -> None:
    _require_f_native_day_step_api()


def test_day_step_f_native_physics_exports_picking_weights_f() -> None:
    _require_picking_weights_f()


def test_day_step_f_native_picking_weights_f_reference_monotone() -> None:
    _require_picking_weights_f()
    f_vals = [0.2, 0.5, 0.9]
    w = ref_picking_weights_f(f_vals, sigma=0.5, uniform=False)
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-12
    assert w[0] < w[1] < w[2]


def test_day_step_f_native_scripted_grid_fixture_shape(
    f_native_scripted_grid: dict[str, Any],
) -> None:
    _require_f_native_day_step_api()
    grid = f_native_scripted_grid
    upl = grid["units_per_lot"]
    offsets = grid["lot_offsets"]
    assert len(grid["freshness"]) == upl * 2
    assert offsets == [0, upl, upl * 2]
    assert alive_by_lot(grid["freshness"], offsets) == [upl, upl]


def test_day_step_f_native_delivery_defaults_units_per_lot_15(
    f_native_delivery_prior: dict[str, Any],
) -> None:
    _require_f_native_day_step_api()
    assert f_native_delivery_prior["units_per_lot"] == 15


def test_day_step_f_native_conservation_rust_tests_pass() -> None:
    """Rust behavioral tests must pass once f-native day_step lands."""
    proc = subprocess.run(
        [
            "cargo",
            "test",
            *_cargo_test_profile(),
            "-p",
            "voi_core",
            "day_step_f_native",
            "--",
            "--nocapture",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
