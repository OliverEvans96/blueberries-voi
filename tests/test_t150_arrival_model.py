"""T-150 — f-native hierarchical arrival model (RED contracts).

Covers Phase 2 artifact/calibration/parity and Phase 3 RPC, recalibration, changelog.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from blueberries_voi.model.abdella import arrival_age_from_path, load_abdella_shipments

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT = _REPO_ROOT / "data" / "abdella" / "arrival_model.json"
_PROVENANCE = _REPO_ROOT / "data" / "abdella" / "PROVENANCE.md"
_CALIB_SCRIPT = _REPO_ROOT / "scripts" / "arrival_calibration_note.py"
_CHANGELOG = _REPO_ROOT / ".team" / "changelog.md"
_PHYSICS_EPOCH_MARKER = _REPO_ROOT / "data" / "abdella" / ".t150_physics_epoch"
_VOI_CRN_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "voi_crn"
_NOTEBOOKS = (
    _REPO_ROOT / "notebooks" / "13_filter_accuracy_knowledge_ladder.ipynb",
    _REPO_ROOT / "notebooks" / "14_gsin_vs_upc_filter_accuracy.ipynb",
)

try:
    from blueberries_voi.backend import rust_core as _maybe_core
except ImportError:
    _maybe_core = None

_REQUIRED_ARTIFACT_KEYS = frozenset(
    {
        "schema_version",
        "mu_T",
        "sigma_T",
        "sigma_pos",
        "q10",
        "T_ref",
        "gamma_shape",
        "gamma_scale",
        "reference_life_days",
        "quadrature",
        "provenance",
    }
)


def _grep_list(pattern: str, root_rel: str) -> list[str]:
    """List repo-relative paths under root_rel whose file contents contain pattern."""
    root = _REPO_ROOT / root_rel
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".venv", "__pycache__", ".git"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pattern in text:
            hits.append(str(path.relative_to(_REPO_ROOT)))
    return hits


def _read(path: Path) -> str:
    assert path.is_file(), f"RED: missing required path {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2 — artifact anchoring (AC2.18)
# ---------------------------------------------------------------------------


def test_ac2_18_arrival_artifact_anchored_to_abdella_shipments() -> None:
    """AC2.18: artifact moments and duration share match parquet observations."""
    shipments = load_abdella_shipments(_REPO_ROOT / "data" / "abdella")
    payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    corridor = payload["corridors"]["abdella_all"]
    q10 = float(payload["q10"])
    t_ref = float(payload["T_ref"])

    d_i = np.asarray([s.duration_d for s in shipments], dtype=float)
    lambda_i = np.asarray(
        [
            arrival_age_from_path(s.temps_c, s.times_d, q10=q10, t_ref_c=t_ref)
            for s in shipments
        ],
        dtype=float,
    )
    phi_i = lambda_i / d_i
    t_i = t_ref + 10.0 * np.log(phi_i) / math.log(q10)

    mu_t_obs = float(np.mean(t_i))
    sigma_t_obs = float(np.std(t_i, ddof=1))
    mu_t_art = float(payload["mu_T"])
    sigma_t_art = float(payload["sigma_T"])

    assert abs(mu_t_art - mu_t_obs) <= 0.5, (
        f"RED: mu_T {mu_t_art} must be within 0.5 C of observed {mu_t_obs:.3f}"
    )
    sigma_ratio = sigma_t_art / sigma_t_obs
    assert 0.5 <= sigma_ratio <= 2.0, (
        f"RED: sigma_T ratio {sigma_ratio:.2f} must be in [0.5, 2.0] "
        f"(artifact={sigma_t_art}, observed sd(T_i)={sigma_t_obs:.3f})"
    )

    e_d_art = float(corridor["d_min"]) + float(corridor["delay_shape"]) * float(
        corridor["delay_scale"]
    )
    sd_d_art = float(corridor["delay_scale"]) * math.sqrt(
        float(corridor["delay_shape"])
    )
    assert abs(e_d_art - float(np.mean(d_i))) <= 0.5, (
        f"RED: E[d] artifact {e_d_art:.3f} vs observed {float(np.mean(d_i)):.3f}"
    )
    sd_ratio = sd_d_art / float(np.std(d_i, ddof=1))
    assert 0.5 <= sd_ratio <= 2.0, (
        f"RED: sd(d) ratio {sd_ratio:.2f} must be in [0.5, 2.0]"
    )

    rng = np.random.default_rng(150_218)
    n_mc = 200_000
    delay_shape = float(corridor["delay_shape"])
    delay_scale = float(corridor["delay_scale"])
    d_min = float(corridor["d_min"])
    d_draw = d_min + rng.gamma(delay_shape, delay_scale, size=n_mc)
    mu_t = float(payload["mu_T"])
    sigma_t = float(payload["sigma_T"])
    t_floor = float(payload.get("temp_floor_c", 0.0))
    t_draw = rng.normal(mu_t, sigma_t, size=n_mc)
    t_draw = np.maximum(t_draw, t_floor)
    phi_draw = np.power(q10, (t_draw - t_ref) / 10.0)
    log_d_var = float(np.var(np.log(d_draw), ddof=0))
    log_phi_var = float(np.var(np.log(phi_draw), ddof=0))
    duration_share = log_d_var / (log_d_var + log_phi_var)
    assert duration_share >= 0.90, (
        f"RED: duration share Var(log d)/Var(log Λ) must be >= 0.90; "
        f"artifact gives {duration_share:.3f}"
    )


# ---------------------------------------------------------------------------
# Phase 2 — artifact, calibration note, Python/Rust parity (AC2.6, AC2.8, AC2.17)
# ---------------------------------------------------------------------------


def test_ac2_6_arrival_artifact_committed_schema() -> None:
    """AC2.6: hand-authored arrival_model.json with versioned schema."""
    assert _ARTIFACT.is_file(), "RED: data/abdella/arrival_model.json must exist"
    payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    missing = _REQUIRED_ARTIFACT_KEYS - set(payload)
    assert not missing, f"RED: artifact missing keys {sorted(missing)}"
    assert payload.get("corridors") or payload.get("arrival_product"), (
        "RED: artifact must key corridors by arrival_product"
    )
    quad = payload["quadrature"]
    assert "nodes" in quad and "weights" in quad, "RED: quadrature spec required"
    prov = _read(_PROVENANCE)
    assert "arrival_model" in prov.lower(), (
        "RED: PROVENANCE.md must document arrival model"
    )


def test_ac2_6_unknown_schema_version_rejected() -> None:
    """AC2.6: parser rejects unknown schema versions (Rust surface via source)."""
    arrival_rs = _REPO_ROOT / "crates" / "voi_core" / "src" / "arrival.rs"
    assert arrival_rs.is_file(), "RED: arrival.rs must exist"
    src = arrival_rs.read_text(encoding="utf-8")
    assert "schema_version" in src and "unknown" in src.lower(), (
        "RED: arrival parser must reject unknown schema versions"
    )


def test_ac2_8_calibration_note_script_and_outputs() -> None:
    """AC2.8: calibration note script reports (no fitting) with required disclosures."""
    assert _CALIB_SCRIPT.is_file(), (
        "RED: scripts/arrival_calibration_note.py must exist"
    )
    src = _CALIB_SCRIPT.read_text(encoding="utf-8")
    assert "parquet" in src, "RED: script must read data/abdella/*.parquet"
    assert (
        "fit" not in src.lower() or "no fit" in src.lower() or "not fit" in src.lower()
    ), "RED: calibration note must not perform fitting"

    note_md = _REPO_ROOT / "data" / "abdella" / "calibration_note.md"
    assert note_md.is_file(), "RED: calibration_note.md must be emitted"
    note = note_md.read_text(encoding="utf-8").lower()
    for phrase in (
        "assumed",
        "six",
        "does not validate",
        "s4",
        "sigma_pos",
        "same refrigerated",
        "upper bound",
        "field heat",
    ):
        assert phrase in note, f"RED: calibration_note.md must mention {phrase!r}"


def test_ac2_17_python_rust_arrival_artifact_parity() -> None:
    """AC2.17: Python/Rust parse the same committed arrival artifact."""
    if _maybe_core is None:
        pytest.skip("blueberries_voi._core not built")

    assert _ARTIFACT.is_file(), "RED: committed arrival_model.json required for parity"

    py_payload = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    for name in ("arrival_model_from_json_py", "parse_arrival_model_py"):
        fn = getattr(_maybe_core, name, None)
        if callable(fn):
            rust_payload = json.loads(fn(str(_ARTIFACT)))
            assert rust_payload["schema_version"] == py_payload["schema_version"]
            assert rust_payload["gamma_scale"] == pytest.approx(
                py_payload["gamma_scale"]
            )
            return
    pytest.fail(
        "RED: Rust must expose arrival_model_from_json_py or parse_arrival_model_py "
        "(mirror demand_profile parity)"
    )


# ---------------------------------------------------------------------------
# Phase 3 — RPC, wire, recalibration, changelog (AC3.1, AC3.3, AC3.6, AC3.7)
# ---------------------------------------------------------------------------


def test_ac3_1_arrival_product_changes_engine_physics() -> None:
    """AC3.1: changing arrival_product chip changes arrival law (not flat ladder)."""
    if _maybe_core is None:
        pytest.skip("blueberries_voi._core not built")

    sess = _maybe_core.PyEngineSession(42)
    sess.init(42)
    base = sess.snapshot_value()
    fn = getattr(sess, "apply_configure", None) or getattr(sess, "configure", None)
    assert callable(fn), "RED: EngineSession must accept RPC configure"

    fn({"arrival_product": "short_haul", "seed": 42})
    short_snap = sess.snapshot_value()
    fn({"arrival_product": "long_haul", "seed": 42})
    long_snap = sess.snapshot_value()

    short_summary = short_snap.get("arrival_summary") or short_snap["result"].get(
        "arrival_summary"
    )
    long_summary = long_snap.get("arrival_summary") or long_snap["result"].get(
        "arrival_summary"
    )
    assert short_summary is not None and long_summary is not None, (
        "RED: snapshot must carry arrival_summary per AC3.3"
    )
    assert short_summary != long_summary, (
        "RED: different arrival_product values must yield different arrival laws"
    )
    _ = base


def test_ac3_3_arrival_summary_includes_f_zero_atom() -> None:
    """AC3.3: wire carries per-rung arrival summary including f=0 atom."""
    if _maybe_core is None:
        pytest.skip("blueberries_voi._core not built")

    sess = _maybe_core.PyEngineSession(7)
    sess.init(7)
    snap = sess.snapshot_value()
    summary = snap.get("arrival_summary") or snap.get("result", {}).get(
        "arrival_summary"
    )
    assert summary is not None, "RED: arrival_summary must be on snapshot wire"
    blob = json.dumps(summary)
    assert "f_zero" in blob or "f=0" in blob or "atom" in blob, (
        "RED: arrival summary must expose the f=0 atom"
    )


def test_ac3_6_recalibration_artifacts_regenerated() -> None:
    """AC3.6: alpha table, VOI CRN snapshots, notebooks after physics epoch."""
    for nb in _NOTEBOOKS:
        assert nb.is_file(), f"RED: notebook {nb.name} must exist for narrative revisit"
    assert _PHYSICS_EPOCH_MARKER.is_file(), (
        "RED: physics-epoch marker data/abdella/.t150_physics_epoch must exist "
        "after alpha tuning, VOI CRN regeneration, and notebook re-run"
    )
    crn_dir = _VOI_CRN_FIXTURES
    crn_snapshots = list(crn_dir.glob("**/*.json")) if crn_dir.is_dir() else []
    assert crn_snapshots, (
        "RED: VOI CRN golden fixtures must be regenerated for T-150 epoch"
    )


def test_ac3_7_changelog_plain_english_entry() -> None:
    """AC3.7: changelog entry for non-technical readers."""
    text = _read(_CHANGELOG).lower()
    for theme in (
        "uncertain",
        "corridor",
        "shelf life",
        "upper bound",
        "field heat",
    ):
        assert theme in text, f"RED: changelog must mention {theme!r} for T-150"


# ---------------------------------------------------------------------------
# Phase 1 — Python-side grep guard complement (AC1.3 allowlist)
# ---------------------------------------------------------------------------


def test_ac1_3_python_legacy_paths_allowlisted() -> None:
    """AC1.3: Python filter/sim may keep age_at_receipt; live package must not."""
    allowed_prefixes = (
        "src/blueberries_voi/filter/",
        "src/blueberries_voi/sim/",
    )
    paths = _grep_list("age_at_receipt", "src/blueberries_voi/")
    outside = [
        p for p in paths if not any(p.startswith(prefix) for prefix in allowed_prefixes)
    ]
    assert not outside, (
        f"RED: age_at_receipt outside Python legacy allowlist: {outside}"
    )
