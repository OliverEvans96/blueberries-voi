"""T-163 v2-guards — clean-chain φ̄ moments (S1.3) and per-day runtime (S1.12)."""

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

# Abdella six-shipment overlay (v2 §3.4.2; T-163 S1.3).
ABDELLA_PHI_BAR_MEAN = 1.36
ABDELLA_PHI_BAR_SD = 0.075
PHI_BAR_MEAN_TOL = 0.02
PHI_BAR_SD_TOL = 0.015

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


def test_clean_chain_phi_bar_moments() -> None:
    """S1.3: v2 artifact + Rust MC guard for clean-chain φ̄ mean/SD at ρ=0."""
    assert _ARTIFACT.is_file(), "RED: data/abdella/arrival_model.json must exist"
    payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    _require_v2_artifact(payload)

    shipments = _SHIPMENTS_RS.read_text(encoding="utf-8")
    assert any(
        needle in shipments
        for needle in ("sigma_hour", "thermal_mode", "trip_mode")
    ), "RED: truth_transit_trace must wire v2 thermal modes / hourly OU"

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


def test_bench_day_timing_within_baseline() -> None:
    """S1.12: release bench_day_timing reports per-day cost near ~5.7 ms/day @ N=200."""
    assert _BENCH_RS.is_file(), "RED: crates/voi_core/src/bin/bench_day_timing.rs must exist"
    cargo_toml = _CARGO_TOML.read_text(encoding="utf-8")
    assert "bench_day_timing" in cargo_toml, (
        "RED: voi_core Cargo.toml must declare [[bin]] bench_day_timing"
    )

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
