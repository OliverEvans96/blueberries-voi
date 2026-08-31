"""T-045 / T-C2-A golden Snapshot / DayDelta fixtures + schema validators — RED.

Locks `.team/specs/T-045.md`, ADR 0100, and T-C2-A f-native wire: committed
goldens under ``tests/fixtures/simulator/``, public ``validate_snapshot`` /
``validate_day_delta``, forbidden presentation keys absent, flat belief
``L`` / ``L*K`` / ``K`` lengths with ``f_grid`` / ``f_marginals``, and live
``EngineSession`` payloads sharing the same helpers (schema + shape).
"""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "simulator"
_SNAPSHOT_GOLDEN = _FIXTURE_DIR / "snapshot_seed42.json"
_DAY_DELTA_GOLDEN = _FIXTURE_DIR / "day_delta_seed42_step0.json"
_STEP_N_GOLDEN = _FIXTURE_DIR / "step_n_seed42.json"
_FIXTURE_README = _FIXTURE_DIR / "README.md"

_SCHEMA_MOD = "blueberries_voi.simulator.schema"
_FIXED_SEED = 42
_RUST_RUNTIME = pytest.mark.skipif(
    _maybe_core is None,
    reason="blueberries_voi._core not built",
)

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "economics",
        "pnl_series",
        "pnl_totals",
        "ghost",
        "ghost_deltas",
        "heatmap",
        "density",
        "ViewModel",
        "view_model",
    }
)

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "f_marginals", "f_grid", "L", "K"})
_LEGACY_BELIEF_KEYS = frozenset({"age_marginals", "tau_grid"})
_SNAPSHOT_REQUIRED = frozenset({"seq", "episode_day", "belief"})
_DAY_DELTA_REQUIRED = frozenset({"seq", "episode_day", "day", "drop_oldest"})


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T045-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T045-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _golden_config(**overrides: Any) -> dict[str, Any]:
    """Match README recipe: filter-on under DEMO_BUDGETS, L=2, K=4, seed 42."""
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": int(DEMO_BUDGETS["n_particles"]),
        "H": int(DEMO_BUDGETS["H"]),
        "n_rollout_paths": int(DEMO_BUDGETS["n_rollout_paths"]),
        "candidate_case_radius": int(DEMO_BUDGETS["candidate_case_radius"]),
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return cfg


def _load_json(path: Path) -> Any:
    assert path.is_file(), f"missing golden fixture: {path.relative_to(_REPO_ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_keys(
    obj: Any, *, found: set[str] | None = None, ancestors: tuple[str, ...] = ()
) -> set[str]:
    out = found if found is not None else set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            sk = str(key)
            if sk == "density" and "arrival_summary" in ancestors:
                _collect_keys(value, found=out, ancestors=(*ancestors, sk))
                continue
            out.add(sk)
            _collect_keys(value, found=out, ancestors=(*ancestors, sk))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            _collect_keys(item, found=out, ancestors=ancestors)
    return out


def _resolve_schema_module() -> Any:
    try:
        return importlib.import_module(_SCHEMA_MOD)
    except ImportError as exc:
        pytest.fail(
            f"{_SCHEMA_MOD} must export validate_snapshot / validate_day_delta "
            f"(T-045 Interfaces); got {exc!r}",
            pytrace=False,
        )


def _resolve_validator(name: str) -> Any:
    mod = _resolve_schema_module()
    fn = getattr(mod, name, None)
    if not callable(fn):
        pytest.fail(
            f"{_SCHEMA_MOD}.{name} must be a callable validator (T-045); got {fn!r}",
            pytrace=False,
        )
    return fn


def _validate_snapshot(obj: Mapping[str, Any]) -> None:
    _resolve_validator("validate_snapshot")(obj)


def _validate_day_delta(obj: Mapping[str, Any]) -> None:
    _resolve_validator("validate_day_delta")(obj)


def _assert_no_forbidden_keys(obj: Any, *, label: str) -> None:
    forbidden = _collect_keys(obj) & _FORBIDDEN_PAYLOAD_KEYS
    assert not forbidden, (
        f"{label} must not contain forbidden presentation keys "
        f"{sorted(forbidden)} (ADR 0100 / T-045)"
    )


def _assert_flat_belief_lengths(belief: Mapping[str, Any], *, label: str) -> None:
    missing = _FLAT_BELIEF_KEYS - set(belief)
    assert not missing, f"{label} missing flat belief fields {sorted(missing)}"
    legacy = _LEGACY_BELIEF_KEYS & set(belief)
    assert not legacy, (
        f"{label} must not expose legacy τ-wire keys {sorted(legacy)} (T-C2-A)"
    )
    l_dim = int(belief["L"])
    k_dim = int(belief["K"])
    lot_counts = list(belief["lot_counts"])
    f_marginals = list(belief["f_marginals"])
    f_grid = list(belief["f_grid"])
    assert len(lot_counts) == l_dim, (
        f"{label}: len(lot_counts)={len(lot_counts)} != L={l_dim}"
    )
    assert len(f_marginals) == l_dim * k_dim, (
        f"{label}: len(f_marginals)={len(f_marginals)} != L*K={l_dim * k_dim}"
    )
    assert len(f_grid) == k_dim, f"{label}: len(f_grid)={len(f_grid)} != K={k_dim}"
    for i, x in enumerate(f_marginals):
        assert not isinstance(x, (list, tuple)), (
            f"{label}.f_marginals[{i}] is nested; wire requires flat L*K"
        )
    for i, f_val in enumerate(f_grid):
        fv = float(f_val)
        assert 0.0 <= fv <= 1.0, f"{label}.f_grid[{i}]={fv} outside freshness [0, 1]"


# ---------------------------------------------------------------------------
# AC: golden fixtures committed under documented path
# ---------------------------------------------------------------------------


def test_fixture_directory_and_readme_document_path() -> None:
    assert _FIXTURE_DIR.is_dir(), (
        "tests/fixtures/simulator/ must exist (T-045 documented golden path)"
    )
    assert _FIXTURE_README.is_file(), (
        "tests/fixtures/simulator/README.md must document path, seed, and "
        "filter-on vs oracle choice"
    )
    text = _FIXTURE_README.read_text(encoding="utf-8").lower()
    assert "filter-on" in text, (
        "fixture README must record filter-on (or oracle) choice"
    )


def test_snapshot_and_day_delta_golden_files_exist() -> None:
    assert _SNAPSHOT_GOLDEN.is_file(), (
        f"committed Snapshot golden missing: {_SNAPSHOT_GOLDEN.name}"
    )
    assert _DAY_DELTA_GOLDEN.is_file(), (
        f"committed DayDelta golden missing: {_DAY_DELTA_GOLDEN.name}"
    )


def test_step_n_framed_golden_file_exists() -> None:
    assert _STEP_N_GOLDEN.is_file(), (
        f"committed step_n framed golden missing: {_STEP_N_GOLDEN.name}"
    )


# ---------------------------------------------------------------------------
# AC: schema helpers validate goldens (required keys + flat belief)
# ---------------------------------------------------------------------------


def test_schema_module_exports_validators() -> None:
    mod = _resolve_schema_module()
    for name in ("validate_snapshot", "validate_day_delta"):
        fn = getattr(mod, name, None)
        assert callable(fn), f"{_SCHEMA_MOD}.{name} must be callable"
        sig = inspect.signature(fn)
        assert len(sig.parameters) >= 1, f"{name} must accept a Mapping payload"


def test_schema_module_flat_belief_keys_f_native() -> None:
    """AC-python-wire: schema._FLAT_BELIEF_KEYS matches f-native wire contract."""
    mod = _resolve_schema_module()
    keys = getattr(mod, "_FLAT_BELIEF_KEYS", None)
    assert keys is not None, f"{_SCHEMA_MOD} must export _FLAT_BELIEF_KEYS"
    assert set(keys) == _FLAT_BELIEF_KEYS, (
        f"{_SCHEMA_MOD}._FLAT_BELIEF_KEYS must be "
        f"{set(_FLAT_BELIEF_KEYS)!r}, got {set(keys)!r}"
    )


def test_golden_snapshot_validates_required_keys_and_flat_belief() -> None:
    snap = _load_json(_SNAPSHOT_GOLDEN)
    assert isinstance(snap, dict)
    missing = _SNAPSHOT_REQUIRED - set(snap)
    assert not missing, f"Snapshot golden missing {sorted(missing)}"
    _validate_snapshot(snap)
    belief = snap["belief"]
    assert isinstance(belief, Mapping)
    _assert_flat_belief_lengths(belief, label="Snapshot golden.belief")
    assert isinstance(snap["seq"], int)
    assert isinstance(snap["episode_day"], int)
    # T-085 / CAL-C1: schedule + demand_summary documented on Snapshot golden.
    assert "schedule" in snap, "Snapshot golden must document schedule (T-085)"
    assert "demand_summary" in snap, (
        "Snapshot golden must document demand_summary (T-085)"
    )
    schedule = snap["schedule"]
    assert isinstance(schedule, Mapping)
    for key in ("delivery_weekdays", "order_weekdays", "lead_time_days", "epoch"):
        assert key in schedule, f"Snapshot golden.schedule missing {key}"
    summary = snap["demand_summary"]
    assert isinstance(summary, Mapping)
    assert "scale_mu" in summary or "scale_target_mu" in summary
    dow = summary.get("dow_means", summary.get("dow_factors"))
    assert isinstance(dow, Sequence) and len(dow) == 7


def test_golden_day_delta_validates_day_and_drop_oldest() -> None:
    delta = _load_json(_DAY_DELTA_GOLDEN)
    assert isinstance(delta, dict)
    missing = _DAY_DELTA_REQUIRED - set(delta)
    assert not missing, f"DayDelta golden missing {sorted(missing)}"
    _validate_day_delta(delta)
    assert isinstance(delta["day"], Mapping)
    assert isinstance(delta["drop_oldest"], bool)
    if delta.get("belief") is not None:
        _assert_flat_belief_lengths(delta["belief"], label="DayDelta golden.belief")


def test_golden_step_n_framed_deltas_validate() -> None:
    framed = _load_json(_STEP_N_GOLDEN)
    assert isinstance(framed, Mapping)
    assert "deltas" in framed, "step_n golden must be framed as {deltas: [...]}"
    deltas = list(framed["deltas"])
    assert len(deltas) == 3, "step_n([0,16,0]) golden must contain 3 DayDeltas"
    for i, delta in enumerate(deltas):
        assert isinstance(delta, Mapping)
        _validate_day_delta(delta)
        assert "drop_oldest" in delta
        _assert_no_forbidden_keys(delta, label=f"step_n golden deltas[{i}]")


# ---------------------------------------------------------------------------
# AC: absence of forbidden presentation keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "label"),
    [
        (_SNAPSHOT_GOLDEN, "Snapshot golden"),
        (_DAY_DELTA_GOLDEN, "DayDelta golden"),
        (_STEP_N_GOLDEN, "step_n golden"),
    ],
)
def test_goldens_exclude_forbidden_presentation_keys(path: Path, label: str) -> None:
    payload = _load_json(path)
    _assert_no_forbidden_keys(payload, label=label)
    # Validators must also reject if those keys were present (contract surface).
    if label.startswith("Snapshot"):
        _validate_snapshot(payload)
    elif label.startswith("DayDelta"):
        _validate_day_delta(payload)


def test_validate_snapshot_rejects_forbidden_economics_key() -> None:
    snap = _load_json(_SNAPSHOT_GOLDEN)
    dirty = dict(snap)
    dirty["economics"] = {"price": 1.0}
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        _validate_snapshot(dirty)


def test_validate_day_delta_rejects_forbidden_heatmap_key() -> None:
    delta = _load_json(_DAY_DELTA_GOLDEN)
    dirty = dict(delta)
    dirty["heatmap"] = [[0.0]]
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        _validate_day_delta(dirty)


def test_validate_snapshot_rejects_nested_density_under_belief() -> None:
    snap = _load_json(_SNAPSHOT_GOLDEN)
    dirty = dict(snap)
    belief = dict(dirty["belief"])
    belief["density"] = [[0.1, 0.2], [0.3, 0.4]]
    dirty["belief"] = belief
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        _validate_snapshot(dirty)


# ---------------------------------------------------------------------------
# AC: flat belief length invariants on goldens
# ---------------------------------------------------------------------------


def test_golden_flat_belief_lengths_match_l_and_k() -> None:
    snap = _load_json(_SNAPSHOT_GOLDEN)
    delta = _load_json(_DAY_DELTA_GOLDEN)
    _assert_flat_belief_lengths(snap["belief"], label="Snapshot golden")
    _assert_flat_belief_lengths(delta["belief"], label="DayDelta golden")
    assert int(snap["belief"]["L"]) == 2
    assert int(snap["belief"]["K"]) == 4
    assert len(snap["belief"]["f_marginals"]) == 8


def _synthetic_f_native_belief(*, l_dim: int = 2, k_dim: int = 4) -> dict[str, Any]:
    """Minimal valid f-native flat belief for validator edge-case tests."""
    f_grid = [i / max(k_dim - 1, 1) for i in range(k_dim)]
    uniform = [1.0 / k_dim] * k_dim
    return {
        "lot_counts": [1.0] * l_dim,
        "f_marginals": uniform * l_dim,
        "f_grid": f_grid,
        "L": l_dim,
        "K": k_dim,
    }


def _synthetic_snapshot(**overrides: Any) -> dict[str, Any]:
    snap = _load_json(_SNAPSHOT_GOLDEN)
    belief = _synthetic_f_native_belief()
    out = dict(snap)
    out["belief"] = belief
    out.update(overrides)
    return out


def test_golden_fixtures_use_f_native_belief_wire() -> None:
    """AC-guards: committed goldens must be regenerated under f-native wire."""
    for path in (_SNAPSHOT_GOLDEN, _DAY_DELTA_GOLDEN, _STEP_N_GOLDEN):
        payload = _load_json(path)
        if "belief" in payload:
            _assert_flat_belief_lengths(payload["belief"], label=path.name)
        elif "deltas" in payload:
            for i, delta in enumerate(payload["deltas"]):
                if delta.get("belief") is not None:
                    _assert_flat_belief_lengths(
                        delta["belief"], label=f"{path.name} deltas[{i}]"
                    )


def test_validate_snapshot_rejects_wrong_f_marginals_length() -> None:
    snap = _synthetic_snapshot()
    dirty = dict(snap)
    belief = dict(dirty["belief"])
    belief["f_marginals"] = list(belief["f_marginals"])[:-1]
    dirty["belief"] = belief
    with pytest.raises(ValueError, match=r"f_marginals"):
        _validate_snapshot(dirty)


def test_validate_snapshot_rejects_nested_f_marginals_rows() -> None:
    snap = _synthetic_snapshot()
    dirty = dict(snap)
    belief = dict(dirty["belief"])
    k_dim = int(belief["K"])
    flat = list(belief["f_marginals"])
    belief["f_marginals"] = [flat[i : i + k_dim] for i in range(0, len(flat), k_dim)]
    dirty["belief"] = belief
    with pytest.raises(TypeError, match=r"nested|flat"):
        _validate_snapshot(dirty)


def test_validate_snapshot_rejects_legacy_tau_wire_keys() -> None:
    snap = _synthetic_snapshot()
    dirty = dict(snap)
    belief = dict(dirty["belief"])
    belief["tau_grid"] = [0.0, 1.0]
    dirty["belief"] = belief
    with pytest.raises(ValueError, match=r"legacy|tau_grid|forbidden"):
        _validate_snapshot(dirty)


def test_validate_day_delta_rejects_missing_drop_oldest() -> None:
    delta = _load_json(_DAY_DELTA_GOLDEN)
    dirty = dict(delta)
    dirty.pop("drop_oldest", None)
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        _validate_day_delta(dirty)


def test_validate_snapshot_rejects_empty_mapping() -> None:
    with pytest.raises((ValueError, TypeError, AssertionError, KeyError)):
        _validate_snapshot({})


def test_validate_day_delta_rejects_non_mapping_day() -> None:
    delta = _load_json(_DAY_DELTA_GOLDEN)
    dirty = dict(delta)
    dirty["day"] = "not-a-day-object"
    with pytest.raises((ValueError, TypeError, AssertionError)):
        _validate_day_delta(dirty)


# ---------------------------------------------------------------------------
# AC: live EngineSession under fixed seed shares schema helpers
# ---------------------------------------------------------------------------


@_RUST_RUNTIME
def test_live_init_snapshot_validates_like_golden() -> None:
    session = EngineSession()
    snap = session.init(_golden_config(), seed=_FIXED_SEED)
    assert isinstance(snap, Mapping)
    _validate_snapshot(snap)
    _assert_no_forbidden_keys(snap, label="live Snapshot")
    _assert_flat_belief_lengths(snap["belief"], label="live Snapshot.belief")
    # Shape parity with golden (byte equality optional).
    golden = _load_json(_SNAPSHOT_GOLDEN)
    assert set(snap.keys()) >= _SNAPSHOT_REQUIRED
    assert set(snap.keys()) == set(golden.keys()) or set(snap) >= set(golden)
    assert int(snap["belief"]["L"]) == int(golden["belief"]["L"])
    assert int(snap["belief"]["K"]) == int(golden["belief"]["K"])


@_RUST_RUNTIME
def test_live_step_day_delta_includes_filter_health() -> None:
    session = EngineSession()
    session.init(_golden_config(), seed=_FIXED_SEED)
    delta = session.step(16)
    assert "filter_health" in delta
    fh = delta["filter_health"]
    assert isinstance(fh, Mapping)
    assert "ess" in fh and "log_evidence" in fh and "infeasible" in fh
    assert float(fh["ess"]) > 0.0
    _validate_day_delta(delta)


@_RUST_RUNTIME
def test_live_step_day_delta_validates_like_golden() -> None:
    session = EngineSession()
    session.init(_golden_config(), seed=_FIXED_SEED)
    delta = session.step(16)
    assert isinstance(delta, Mapping)
    _validate_day_delta(delta)
    _assert_no_forbidden_keys(delta, label="live DayDelta")
    assert "drop_oldest" in delta
    assert isinstance(delta["drop_oldest"], bool)
    if delta.get("belief") is not None:
        _assert_flat_belief_lengths(delta["belief"], label="live DayDelta.belief")
    golden = _load_json(_DAY_DELTA_GOLDEN)
    assert set(delta.keys()) >= _DAY_DELTA_REQUIRED
    assert set(delta.keys()) == set(golden.keys()) or set(delta) >= _DAY_DELTA_REQUIRED


@_RUST_RUNTIME
def test_live_step_n_deltas_validate_with_same_helpers() -> None:
    session = EngineSession()
    session.init(_golden_config(), seed=_FIXED_SEED)
    orders = [0, 16, 0]
    # EngineSession.step_n is typed list[DayDelta]; framed {deltas: [...]}
    # remains allowed by ADR 0100 — accept either shape at runtime.
    result: Any = session.step_n(orders)
    if isinstance(result, Mapping) and "deltas" in result:
        deltas = list(result["deltas"])
    else:
        assert isinstance(result, list)
        deltas = result
    assert len(deltas) == len(orders)
    for i, delta in enumerate(deltas):
        _validate_day_delta(delta)
        _assert_no_forbidden_keys(delta, label=f"live step_n[{i}]")
        assert "drop_oldest" in delta


@_RUST_RUNTIME
def test_live_snapshot_json_round_trip_excludes_presentation_keys() -> None:
    session = EngineSession()
    snap = session.init(_golden_config(), seed=_FIXED_SEED)
    encoded = json.dumps(snap)
    decoded = json.loads(encoded)
    assert isinstance(decoded, dict)
    _validate_snapshot(decoded)
    _assert_no_forbidden_keys(decoded, label="live Snapshot json round-trip")
