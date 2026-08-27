"""T-163 v2-artifact shard — fit script honesty and v2 schema (RED)."""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT = _REPO_ROOT / "data" / "abdella" / "arrival_model.json"
_FIT_SCRIPT = _REPO_ROOT / "scripts" / "fit_abdella_arrival.py"
_CALIB_NOTE = _REPO_ROOT / "data" / "abdella" / "calibration_note.md"
_FIT_REPORT = _REPO_ROOT / "data" / "abdella" / "fit_report.md"


def _fit_script_source() -> str:
    return _FIT_SCRIPT.read_text(encoding="utf-8")


def _build_artifact_section() -> str:
    src = _fit_script_source()
    return src.split("def _build_artifact")[1].split("def _write_overlay")[0]


def _load_artifact() -> dict:
    return json.loads(_ARTIFACT.read_text(encoding="utf-8"))


def test_committed_artifact_has_v2_thermal_fields() -> None:
    """S1.9 — artifact exposes trip modes and hourly OU."""
    payload = _load_artifact()
    assert "thermal_modes" in payload, "missing thermal_modes"
    modes = payload["thermal_modes"]
    for mode in ("cool", "nominal", "warm"):
        assert mode in modes, f"thermal_modes missing {mode}"
        assert "offset_c" in modes[mode]
        assert "p" in modes[mode]
    assert "sigma_hour" in payload
    assert float(payload["sigma_hour"]) > 0.0


def test_fit_script_build_artifact_fits_duration_only() -> None:
    """S1.10 — no truncated-normal temperature fit in artifact builder."""
    section = _build_artifact_section()
    assert "_fit_truncated_normal_t" not in section, (
        "fit script must not call truncated-normal temperature fit"
    )
    for retired in ('"mu_T"', '"sigma_T"', '"temp_floor_c"'):
        assert retired not in section, f"builder must not emit retired key {retired}"


def test_fit_script_documents_assumed_thermal_modes_sigma_hour_and_breaks() -> None:
    """S1.10 — provenance documents assumed modes, sigma_hour, and break knobs."""
    src = _fit_script_source().lower()
    for needle in ("thermal_modes", "sigma_hour", "t_break", "tau_bar", "assumed"):
        assert needle in src, f"fit script must document v2 assumed knob {needle!r}"


def test_fit_report_documents_assumed_not_fitted_thermal_knobs() -> None:
    """S1.10 — fit report distinguishes fitted duration from assumed thermal fields."""
    text = _FIT_REPORT.read_text(encoding="utf-8").lower()
    assert "mu_t" not in text, "fit report must retire truncated-normal mu_T"
    assert "sigma_t" not in text, "fit report must retire truncated-normal sigma_T"
    for phrase in ("thermal_modes", "sigma_hour", "assumed"):
        assert phrase in text, f"fit_report.md must document {phrase!r}"


def test_calibration_note_reports_design_variance_decomposition() -> None:
    """S1.12 — design share of Var(log Λ) at default rho (duration vs breaks)."""
    note = _CALIB_NOTE.read_text(encoding="utf-8").lower()
    assert "var(log" in note or ("variance" in note and "log" in note), (
        "calibration note must report Var(log Λ) decomposition"
    )
    assert "duration" in note and "break" in note, (
        "calibration note must split duration vs break variance share"
    )
