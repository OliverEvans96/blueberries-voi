"""T-081 / ADR 0148: Abdella arrival_model.json fit product (FreshNet parity)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT = _REPO_ROOT / "data" / "abdella" / "arrival_model.json"
_FIT_REPORT = _REPO_ROOT / "data" / "abdella" / "fit_report.md"
_FIT_SCRIPT = _REPO_ROOT / "scripts" / "fit_abdella_arrival.py"
_CALIB_SCRIPT = _REPO_ROOT / "scripts" / "arrival_calibration_note.py"
_PROVENANCE = _REPO_ROOT / "data" / "abdella" / "PROVENANCE.md"
_NOTE = _REPO_ROOT / "data" / "abdella" / "calibration_note.md"


def test_abdella_arrival_artifact_exists() -> None:
    assert _ARTIFACT.is_file()
    payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert "abdella_all" in payload["corridors"]
    assert "abdella_mix" in payload.get("corridor_mixtures", {})
    prov = payload.get("provenance", {})
    assert prov.get("fit_script") == "scripts/fit_abdella_arrival.py"
    assert "fitted_fields" in prov and "adjustment_fields" in prov


def test_abdella_fit_report_documents_adjustment_knobs() -> None:
    assert _FIT_REPORT.is_file()
    text = _FIT_REPORT.read_text(encoding="utf-8").lower()
    assert "adjustment knobs" in text
    assert "gamma_shape" in text
    assert "honesty" in text


def test_fit_abdella_script_exists() -> None:
    assert _FIT_SCRIPT.is_file()
    src = _FIT_SCRIPT.read_text(encoding="utf-8")
    assert "arrival_model.json" in src
    assert "fit_report.md" in src


def test_calibration_note_script_is_reporting_only() -> None:
    assert _CALIB_SCRIPT.is_file()
    src = _CALIB_SCRIPT.read_text(encoding="utf-8").lower()
    assert "fit_abdella_arrival" in src
    assert "arrival_model.json" in src
    assert "load_abdella_shipments" in src
    assert "fit_report" not in src


def test_provenance_documents_fit_workflow() -> None:
    prov = _PROVENANCE.read_text(encoding="utf-8").lower()
    assert "fit_abdella_arrival" in prov
    assert "fit_report" in prov


def test_calibration_note_disclosures() -> None:
    assert _NOTE.is_file()
    note = _NOTE.read_text(encoding="utf-8").lower()
    for phrase in (
        "fitted",
        "six",
        "does not validate",
        "s4",
        "sigma_pos",
        "same refrigerated",
        "upper bound",
        "field heat",
    ):
        assert phrase in note, f"calibration_note.md must mention {phrase!r}"


def test_arrival_model_profile_loads_without_parquet() -> None:
    from blueberries_voi.model.arrival_model_profile import (
        exposure_prior_on_grid,
        load_arrival_model,
    )

    payload = load_arrival_model(_ARTIFACT)
    grid = np.linspace(0.0, 8.0, 17)
    prior = exposure_prior_on_grid(grid, payload)
    assert float(prior.sum()) == pytest.approx(1.0, abs=1e-6)


def test_default_shipments_no_parquet() -> None:
    from blueberries_voi.sim.shipments import default_shipments

    ships = default_shipments()
    assert len(ships) == 6
    assert all(len(s.temps_c) == 2 for s in ships)


def test_arrival_priors_use_fitted_model_not_parquet() -> None:
    from blueberries_voi.filter import arrival_priors

    src = inspect.getsource(arrival_priors)
    assert "arrival_model_profile" in src
    assert "load_abdella_shipments" not in src
