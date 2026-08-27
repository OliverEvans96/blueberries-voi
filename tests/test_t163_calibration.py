"""T-163 v2-guards — clean-chain φ̄ moments (S1.3) and per-day runtime (S1.12).

Fast path: static artifact / wiring checks (default ``uv run pytest``).
MC + bench subprocess guards are ``slow`` — CI ``cargo test --release`` is canonical.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT = _REPO_ROOT / "data" / "abdella" / "arrival_model.json"
_BENCH_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "bin" / "bench_day_timing.rs"
_CARGO_TOML = _REPO_ROOT / "crates" / "voi_core" / "Cargo.toml"
_SHIPMENTS_RS = _REPO_ROOT / "crates" / "voi_core" / "src" / "shipments.rs"

# Production filter_step_unit @ N=200, L=20 (handoff / c2_a_totals_study).
BASELINE_MS_PER_DAY = 5.7
RUNTIME_NOISE_FACTOR = 1.5  # within-noise upper bound for v2 birth-path changes


def _cargo_test_profile() -> tuple[str, ...]:
    profile: tuple[str, ...] = ("--locked",)
    if os.environ.get("CI", "").lower() == "true":
        profile = ("--release", *profile)
    return profile


def _require_v2_artifact(payload: dict[str, object]) -> None:
    for key in ("sigma_hour", "thermal_modes"):
        assert key in payload, f"RED: arrival artifact must carry v2 field {key!r}"


def test_clean_chain_phi_bar_v2_wiring() -> None:
    """S1.3 fast guard — v2 artifact fields and generative wiring (MC in Rust CI)."""
    assert _ARTIFACT.is_file(), "RED: data/abdella/arrival_model.json must exist"
    payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    _require_v2_artifact(payload)

    shipments = _SHIPMENTS_RS.read_text(encoding="utf-8")
    assert any(
        needle in shipments
        for needle in ("sigma_hour", "thermal_mode", "trip_mode")
    ), "RED: truth_transit_trace must wire v2 thermal modes / hourly OU"


@pytest.mark.slow
def test_clean_chain_phi_bar_moments_rust_mc() -> None:
    """S1.3 MC guard — delegates to ``t163_v2_calibration`` (also in ``cargo test`` CI)."""
    proc = subprocess.run(
        [
            "cargo",
            "test",
            *_cargo_test_profile(),
            "-p",
            "voi_core",
            "--test",
            "t163_v2_calibration",
            "clean_chain_phi_bar_moments",
            "--",
            "--exact",
            "--nocapture",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bench_day_timing_registered() -> None:
    """S1.12 fast guard — bench binary exists (runtime measured in slow / verify)."""
    assert _BENCH_RS.is_file(), "RED: crates/voi_core/src/bin/bench_day_timing.rs must exist"
    cargo_toml = _CARGO_TOML.read_text(encoding="utf-8")
    assert "bench_day_timing" in cargo_toml, (
        "RED: voi_core Cargo.toml must declare [[bin]] bench_day_timing"
    )


@pytest.mark.slow
def test_bench_day_timing_within_baseline() -> None:
    """S1.12: release bench_day_timing reports per-day cost near ~5.7 ms/day @ N=200."""
    test_bench_day_timing_registered()

    proc = subprocess.run(
        [
            "cargo",
            "run",
            "--release",
            "--locked",
            "-p",
            "voi_core",
            "--bin",
            "bench_day_timing",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "OMP_NUM_THREADS": "1"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    combined = proc.stdout + proc.stderr
    match = re.search(r"mean\s+ms(?:/day)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", combined, re.I)
    assert match is not None, (
        f"RED: bench_day_timing must print mean ms/day; got:\n{combined}"
    )
    mean_ms = float(match.group(1))
    upper = BASELINE_MS_PER_DAY * RUNTIME_NOISE_FACTOR
    assert mean_ms <= upper, (
        f"RED: per-day cost {mean_ms:.3f} ms exceeds noise band "
        f"({BASELINE_MS_PER_DAY} ms baseline × {RUNTIME_NOISE_FACTOR})"
    )
