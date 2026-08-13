"""T-043 EngineSession façade + closed-loop day driver — RED contracts.

Locks `.team/specs/T-043.md`, ADR 0099 (dialed demo budgets), and ADR 0100
(Snapshot / DayDelta / flat belief wire; no ViewModel / economics / PnL /
ghost / heatmap on the Python return path).

No production ``simulator/`` code in this worktree — tests must fail for
missing module/API or wrong behaviour, not import typos.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.controller.rollout import (
    DEFAULT_CANDIDATE_CASE_RADIUS,
    DEFAULT_N_ROLLOUT_PATHS,
    DEFAULT_ROLLOUT_H,
)
from blueberries_voi.filter import PRODUCTION_N
from blueberries_voi.model.abdella import ShipmentTrace

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SIMULATOR_PKG = "blueberries_voi.simulator"
_ENGINE_SESSION = "EngineSession"
_SRC_SIMULATOR = _REPO_ROOT / "src" / "blueberries_voi" / "simulator"

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
_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyplot", "pyarrow"})

# ADR 0099 / T-043 dialed browser demo caps (must be ≤ production defaults).
_DEMO_N_PARTICLES_CAP = 200
_DEMO_H_CAP = 7
_DEMO_N_ROLLOUT_PATHS_CAP = 2
_DEMO_CANDIDATE_RADIUS_CAP = 1

_FLAT_BELIEF_KEYS = frozenset({"lot_counts", "age_marginals", "tau_grid", "L", "K"})
_SNAPSHOT_TOP_KEYS = frozenset({"seq", "episode_day", "belief"})
_DAY_DELTA_TOP_KEYS = frozenset({"seq", "episode_day", "day"})


def _fixture_shipments() -> list[ShipmentTrace]:
    """In-memory traces — session must not require parquet / Abdella FS."""
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T043-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T043-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _minimal_config(**overrides: Any) -> dict[str, Any]:
    """Dialed demo-ish config; shipments injected (no parquet)."""
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": 32,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
    }
    cfg.update(overrides)
    return cfg


def _resolve_simulator_module() -> Any:
    try:
        return importlib.import_module(_SIMULATOR_PKG)
    except ImportError as exc:
        pytest.fail(
            f"{_SIMULATOR_PKG} must be importable per T-043 "
            f"(src/blueberries_voi/simulator/); got {exc!r}",
            pytrace=False,
        )


def _resolve_engine_session_cls() -> type[Any]:
    mod = _resolve_simulator_module()
    cls = getattr(mod, _ENGINE_SESSION, None)
    if cls is None or not inspect.isclass(cls):
        pytest.fail(
            f"{_ENGINE_SESSION} must be exported from {_SIMULATOR_PKG} "
            "(T-043 / ADR 0100)",
            pytrace=False,
        )
    return cls


def _new_session() -> Any:
    return _resolve_engine_session_cls()()


def _as_mapping(payload: Any, *, label: str) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if hasattr(payload, "keys") and hasattr(payload, "__getitem__"):
        return dict(payload)
    pytest.fail(f"{label} must be a Mapping/dict wire payload, got {type(payload)!r}")


def _collect_keys(obj: Any, *, found: set[str] | None = None) -> set[str]:
    """Recursively collect string keys from nested dict/list payloads."""
    out = found if found is not None else set()
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            out.add(str(key))
            _collect_keys(value, found=out)
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            _collect_keys(item, found=out)
    return out


def _assert_json_round_trip(payload: Mapping[str, Any], *, label: str) -> Any:
    try:
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"{label} must JSON round-trip (ADR 0100); got {exc!r}")
    assert isinstance(decoded, dict), f"{label} json.loads must yield a dict"
    forbidden = _collect_keys(decoded) & _FORBIDDEN_PAYLOAD_KEYS
    assert not forbidden, (
        f"{label} must not contain forbidden presentation keys {sorted(forbidden)} "
        "(ADR 0100: no economics / PnL / ghost / heatmap / density / ViewModel)"
    )
    return decoded


def _assert_flat_belief(belief: Any, *, label: str) -> Mapping[str, Any]:
    bel = _as_mapping(belief, label=f"{label}.belief")
    missing = _FLAT_BELIEF_KEYS - set(bel)
    assert not missing, (
        f"{label}.belief missing flat fields {sorted(missing)} (ADR 0100)"
    )
    lot_counts = list(bel["lot_counts"])
    age_marginals = list(bel["age_marginals"])
    tau_grid = list(bel["tau_grid"])
    l_dim = int(bel["L"])
    k_dim = int(bel["K"])
    assert l_dim >= 0 and k_dim >= 0
    assert len(lot_counts) == l_dim, (
        f"{label}: lot_counts length {len(lot_counts)} != L={l_dim}"
    )
    assert len(age_marginals) == l_dim * k_dim, (
        f"{label}: age_marginals length {len(age_marginals)} != L*K={l_dim * k_dim} "
        "(flat row-major)"
    )
    assert len(tau_grid) == k_dim, (
        f"{label}: tau_grid length {len(tau_grid)} != K={k_dim}"
    )
    # Flat wire: age_marginals must be 1-D list of floats, not nested rows.
    for i, x in enumerate(age_marginals):
        assert not isinstance(x, (list, tuple)), (
            f"{label}.belief.age_marginals[{i}] is nested; wire requires flat L*K "
            "(ADR 0100)"
        )
        float(x)
    for x in lot_counts:
        float(x)
    for t in tau_grid:
        float(t)
    return bel


def _assert_snapshot(payload: Any, *, label: str = "Snapshot") -> Mapping[str, Any]:
    snap = _as_mapping(payload, label=label)
    missing = _SNAPSHOT_TOP_KEYS - set(snap)
    assert not missing, f"{label} missing top-level keys {sorted(missing)}"
    assert isinstance(snap["seq"], int)
    assert isinstance(snap["episode_day"], int)
    _assert_flat_belief(snap["belief"], label=label)
    _assert_json_round_trip(snap, label=label)
    return snap


def _assert_day_delta(payload: Any, *, label: str = "DayDelta") -> Mapping[str, Any]:
    delta = _as_mapping(payload, label=label)
    missing = _DAY_DELTA_TOP_KEYS - set(delta)
    assert not missing, f"{label} missing top-level keys {sorted(missing)}"
    assert isinstance(delta["seq"], int)
    assert isinstance(delta["episode_day"], int)
    assert isinstance(delta["day"], Mapping) or hasattr(delta["day"], "keys"), (
        f"{label}.day must be a single day object/mapping"
    )
    if "belief" in delta and delta["belief"] is not None:
        _assert_flat_belief(delta["belief"], label=label)
    _assert_json_round_trip(delta, label=label)
    return delta


def _normalize_step_n_result(result: Any, *, k: int) -> list[Any]:
    if isinstance(result, list):
        deltas = result
    elif isinstance(result, Mapping) and "deltas" in result:
        deltas = list(result["deltas"])
    else:
        pytest.fail(
            "step_n must return list[DayDelta] or a framed object with "
            f"`deltas` of length {k}; got {type(result)!r}"
        )
    assert len(deltas) == k, f"step_n({k}) must yield exactly {k} DayDeltas"
    return deltas


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", maxsplit=1)[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
            imported.add(node.module)
    return imported


def _simulator_py_files() -> list[Path]:
    if not _SRC_SIMULATOR.is_dir():
        pytest.fail(
            "src/blueberries_voi/simulator/ package directory must exist (T-043)",
            pytrace=False,
        )
    files = sorted(_SRC_SIMULATOR.rglob("*.py"))
    assert files, "simulator/ must contain at least one .py module"
    return files


def _resolve_demo_budget_preset(mod: Any) -> Mapping[str, Any]:
    """Locate documented browser demo budget preset (name may vary)."""
    candidates = (
        "DEMO_BUDGETS",
        "BROWSER_DEMO_BUDGETS",
        "DEMO_BUDGET_PRESET",
        "BROWSER_DEMO_PRESET",
        "demo_budgets",
        "browser_demo_budgets",
    )
    for name in candidates:
        got = getattr(mod, name, None)
        if got is None:
            continue
        if callable(got):
            got = got()
        if isinstance(got, Mapping):
            return got
    session_cls = getattr(mod, _ENGINE_SESSION, None)
    if session_cls is not None:
        for name in candidates:
            got = getattr(session_cls, name, None)
            if got is None:
                continue
            if callable(got):
                got = got()
            if isinstance(got, Mapping):
                return got
    pytest.fail(
        "simulator must document a browser demo budget preset "
        f"(tried {candidates}) with n_particles/H/n_rollout_paths/"
        "candidate radius ≤ ADR 0099 caps",
        pytrace=False,
    )


def _budget_value(preset: Mapping[str, Any], *names: str) -> int:
    for name in names:
        if name in preset:
            return int(preset[name])
    pytest.fail(
        f"demo preset missing budget knob among {names}; keys={sorted(preset)}",
        pytrace=False,
    )


# ---------------------------------------------------------------------------
# AC: package importable
# ---------------------------------------------------------------------------


def test_simulator_package_importable() -> None:
    mod = _resolve_simulator_module()
    assert mod.__name__ == _SIMULATOR_PKG


def test_simulator_package_directory_exists() -> None:
    assert _SRC_SIMULATOR.is_dir(), (
        "src/blueberries_voi/simulator/ must exist and be a package (T-043)"
    )
    assert (_SRC_SIMULATOR / "__init__.py").is_file()


# ---------------------------------------------------------------------------
# AC: EngineSession methods
# ---------------------------------------------------------------------------


def test_engine_session_exported() -> None:
    cls = _resolve_engine_session_cls()
    assert cls.__name__ == _ENGINE_SESSION


@pytest.mark.parametrize(
    "method_name",
    ["init", "step", "step_n", "reset", "act"],
)
def test_engine_session_exposes_required_methods(method_name: str) -> None:
    cls = _resolve_engine_session_cls()
    method = getattr(cls, method_name, None)
    assert callable(method), (
        f"EngineSession.{method_name} must be a callable method (T-043 Interfaces)"
    )


def test_engine_session_method_signatures_match_interfaces() -> None:
    cls = _resolve_engine_session_cls()
    init_sig = inspect.signature(cls.init)
    assert "config" in init_sig.parameters
    assert "seed" in init_sig.parameters

    reset_sig = inspect.signature(cls.reset)
    assert "seed" in reset_sig.parameters

    step_sig = inspect.signature(cls.step)
    assert "order_qty" in step_sig.parameters

    step_n_sig = inspect.signature(cls.step_n)
    assert "orders" in step_n_sig.parameters

    act_sig = inspect.signature(cls.act)
    # policy optional; budget overrides via **kwargs
    assert any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in act_sig.parameters.values()
    ) or {"n_particles", "H", "n_rollout_paths"}.intersection(act_sig.parameters), (
        "act must accept budget overrides (**budget_overrides or named knobs)"
    )


# ---------------------------------------------------------------------------
# AC: init / reset → Snapshot with flat belief
# ---------------------------------------------------------------------------


def test_init_returns_snapshot_with_flat_belief() -> None:
    session = _new_session()
    snap = session.init(_minimal_config(), seed=7)
    decoded = _assert_snapshot(snap, label="init Snapshot")
    assert decoded["seq"] >= 0
    assert decoded["episode_day"] >= 0


def test_reset_returns_snapshot_with_flat_belief() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=3)
    snap = session.reset(_minimal_config(n_particles=16), seed=11)
    _assert_snapshot(snap, label="reset Snapshot")


def test_reset_without_config_reuses_session() -> None:
    session = _new_session()
    first = _assert_snapshot(session.init(_minimal_config(), seed=5))
    second = _assert_snapshot(session.reset(seed=5), label="reset(None) Snapshot")
    # Same seed + config → deterministic cold start fields at least present.
    assert "belief" in second
    assert first["belief"]["K"] == second["belief"]["K"]


# ---------------------------------------------------------------------------
# AC: step / step_n → DayDelta
# ---------------------------------------------------------------------------


def test_step_returns_day_delta() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=1)
    delta = session.step(0)
    _assert_day_delta(delta, label="step DayDelta")


def test_step_n_returns_exactly_k_day_deltas() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=2)
    orders = [0, 8, 0, 16]
    result = session.step_n(orders)
    deltas = _normalize_step_n_result(result, k=len(orders))
    for i, delta in enumerate(deltas):
        _assert_day_delta(delta, label=f"step_n[{i}]")


def test_step_n_empty_orders_returns_empty_sequence() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=4)
    result = session.step_n([])
    deltas = _normalize_step_n_result(result, k=0)
    assert deltas == []


def test_step_before_init_raises() -> None:
    session = _new_session()
    with pytest.raises((RuntimeError, ValueError, AssertionError)):
        session.step(0)


def test_step_rejects_non_int_order_qty() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=9)
    with pytest.raises((TypeError, ValueError)):
        session.step("eight")


# ---------------------------------------------------------------------------
# AC: JSON round-trip + forbidden presentation keys
# ---------------------------------------------------------------------------


def test_snapshot_and_day_delta_json_round_trip_excludes_presentation_keys() -> None:
    session = _new_session()
    snap = session.init(_minimal_config(), seed=13)
    delta = session.step(8)
    for label, payload in (("Snapshot", snap), ("DayDelta", delta)):
        decoded = _assert_json_round_trip(
            _as_mapping(payload, label=label), label=label
        )
        # Explicit top-level ban as well as recursive.
        for key in _FORBIDDEN_PAYLOAD_KEYS:
            assert key not in decoded, f"{label} must not have top-level key {key!r}"


# ---------------------------------------------------------------------------
# AC: act selects via controller + advances like step
# ---------------------------------------------------------------------------


def test_act_returns_day_delta_and_accepts_budget_knobs() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=17)
    delta = session.act(
        policy="constant",
        n_particles=16,
        H=2,
        n_rollout_paths=1,
        candidate_case_radius=1,
    )
    _assert_day_delta(delta, label="act DayDelta")


def test_act_advances_equivalently_to_step_with_same_order() -> None:
    """act(...) must match step(order) DayDelta shape (and seq progression).

    Uses a deterministic constant policy when available; otherwise compares
    structural DayDelta keys after a single advance from identical seeds.
    """
    cls = _resolve_engine_session_cls()
    cfg = _minimal_config()

    session_act = cls()
    session_act.init(cfg, seed=21)
    # Prefer constant / fixed order if the façade documents it.
    try:
        delta_act = session_act.act(policy="constant", order_qty=8)
    except TypeError:
        delta_act = session_act.act(policy="constant")
    except (ValueError, KeyError):
        # Fall back: any actable policy still yields DayDelta shape parity.
        delta_act = session_act.act(H=2, n_rollout_paths=1)

    act_map = _assert_day_delta(delta_act, label="act")

    session_step = cls()
    session_step.init(cfg, seed=21)
    # If act recorded applied order on the day object, reuse it; else step(0).
    day_obj = act_map["day"]
    order_qty = 0
    if isinstance(day_obj, Mapping):
        for key in ("order_qty", "order", "q", "ordered_units"):
            if key in day_obj:
                order_qty = int(day_obj[key])
                break
    delta_step = session_step.step(order_qty)
    step_map = _assert_day_delta(delta_step, label="step twin")

    assert set(act_map.keys()) == set(step_map.keys()) or (
        set(act_map) >= _DAY_DELTA_TOP_KEYS and set(step_map) >= _DAY_DELTA_TOP_KEYS
    ), "act and step must share DayDelta shape (T-043)"
    assert act_map["episode_day"] == step_map["episode_day"]


# ---------------------------------------------------------------------------
# AC: first-class budget knobs + dialed demo preset
# ---------------------------------------------------------------------------


def test_session_accepts_first_class_budget_knobs_on_init() -> None:
    session = _new_session()
    snap = session.init(
        _minimal_config(
            n_particles=64,
            H=5,
            n_rollout_paths=2,
            candidate_case_radius=1,
        ),
        seed=0,
    )
    snap_map = _assert_snapshot(snap)
    applied = snap_map.get("applied_config")
    if isinstance(applied, Mapping):
        for key in ("n_particles", "H", "n_rollout_paths"):
            if key in applied:
                assert int(applied[key]) > 0


def test_browser_demo_budget_preset_within_dialed_caps() -> None:
    mod = _resolve_simulator_module()
    preset = _resolve_demo_budget_preset(mod)
    n_particles = _budget_value(preset, "n_particles", "N", "n")
    horizon = _budget_value(preset, "H", "horizon", "rollout_H")
    n_paths = _budget_value(preset, "n_rollout_paths", "n_paths")
    radius = _budget_value(
        preset,
        "candidate_case_radius",
        "candidate_radius",
        "radius",
    )

    assert n_particles <= _DEMO_N_PARTICLES_CAP
    assert horizon <= _DEMO_H_CAP
    assert n_paths <= _DEMO_N_ROLLOUT_PATHS_CAP
    assert radius <= _DEMO_CANDIDATE_RADIUS_CAP

    # Must be dialed relative to production / desktop defaults (ADR 0099).
    assert n_particles <= int(PRODUCTION_N)
    assert horizon <= int(DEFAULT_ROLLOUT_H)
    assert n_paths <= int(DEFAULT_N_ROLLOUT_PATHS)
    assert radius <= int(DEFAULT_CANDIDATE_CASE_RADIUS)


# ---------------------------------------------------------------------------
# AC: shared day driver purity (no matplotlib / pyarrow)
# ---------------------------------------------------------------------------


def test_simulator_modules_have_no_matplotlib_or_pyarrow_imports() -> None:
    for path in _simulator_py_files():
        roots = _imported_roots(path)
        banned = roots & _FORBIDDEN_IMPORT_ROOTS
        assert not banned, (
            f"{path.relative_to(_REPO_ROOT)} must not import {sorted(banned)} "
            "(T-043 shared day driver / browser path)"
        )


def test_shared_day_driver_symbol_exists() -> None:
    """Session must use a shared closed-loop day driver (name may vary)."""
    mod = _resolve_simulator_module()
    candidates = (
        "advance_day",
        "run_day",
        "day_driver",
        "closed_loop_day",
        "step_day",
        "drive_day",
    )
    found = None
    for name in candidates:
        got = getattr(mod, name, None)
        if callable(got):
            found = got
            break
    if found is None:
        # Also accept a submodule that exports the driver.
        for sub in ("day_driver", "driver", "loop", "session"):
            try:
                submod = importlib.import_module(f"{_SIMULATOR_PKG}.{sub}")
            except ImportError:
                continue
            for name in candidates:
                got = getattr(submod, name, None)
                if callable(got):
                    found = got
                    break
            if found is not None:
                break
    assert found is not None, (
        "simulator must expose a shared day driver callable "
        f"(tried {candidates} on package / day_driver|driver|loop|session) "
        "performing order→pending/arrival→day_step→obs→optional RBPF→belief→DayDelta"
    )
