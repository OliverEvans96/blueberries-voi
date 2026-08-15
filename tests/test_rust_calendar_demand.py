"""T-121c (Wave C): Calendar demand (CAL-01) in Rust — RED before C1/C3/C4.

References Python ``demand_profile.py`` and committed
``data/freshnet/demand_profile.json``. Does not implement Rust.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.model.demand_profile import load_demand_profile
from blueberries_voi.simulator.session import EngineSession

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMAND_PROFILE_PATH = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_GOLDEN_DAYS = (0, 6, 7, 13, 89)
_EPISODE_DAYS = 90
_MU_ABS_TOL = 1e-9
_FLAT_MU = 30.0
_SESSION_SEED = 42
_VOI_SEED = 77


def _require_rust_core() -> Any:
    if _maybe_core is None:
        pytest.fail(
            "blueberries_voi._core not built; run maturin develop -m crates/voi_py/Cargo.toml"
        )
    return _maybe_core


def _require_demand_profile_mu_from_json_py() -> Any:
    core = _require_rust_core()
    fn = getattr(core, "demand_profile_mu_from_json_py", None)
    if fn is None:
        pytest.fail(
            "rust_core must expose demand_profile_mu_from_json_py(json, day) for T-121c C1"
        )
    return fn


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def _committed_profile() -> Any:
    assert _DEMAND_PROFILE_PATH.is_file(), (
        "committed data/freshnet/demand_profile.json required (T-121c / CAL-01)"
    )
    return load_demand_profile(_DEMAND_PROFILE_PATH)


def _profile_json_text() -> str:
    return _DEMAND_PROFILE_PATH.read_text(encoding="utf-8")


def _ships() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T121c",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _ship_times_temps() -> tuple[list[list[float]], list[list[float]]]:
    ships = _ships()
    times = [list(map(float, s.times_d)) for s in ships]
    temps = [list(map(float, s.temps_c)) for s in ships]
    return times, temps


def _cfg(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _ships(),
        "n_particles": 32,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": True,
        "lead_time": 1,
    }
    cfg.update(overrides)
    return cfg


def _rust_session_mean_demand(
    *,
    seed: int,
    n_days: int,
    demand_profile_json: str | None,
) -> float:
    session = EngineSession()
    overrides: dict[str, Any] = {}
    if demand_profile_json is not None:
        overrides["demand_profile"] = load_demand_profile(_DEMAND_PROFILE_PATH)
        overrides["demand_profile_json"] = demand_profile_json
    session.init(_cfg(**overrides), seed=seed)
    demands: list[int] = []
    for _ in range(n_days):
        delta = session.step(0)
        demands.append(int(delta["day"]["demand"]))
    return float(np.mean(demands))


def _voi_episode_demands(
    *,
    seed: int,
    n_days: int,
    demand_profile_json: str | None,
) -> list[int]:
    core = _require_rust_core()
    times, temps = _ship_times_temps()
    ep_fn = getattr(core, "run_voi_crn_episode_demands_py", None)
    if ep_fn is not None:
        sig = inspect.signature(ep_fn)
        kwargs: dict[str, Any] = {}
        if "demand_profile_json" in sig.parameters:
            kwargs["demand_profile_json"] = demand_profile_json
        try:
            raw = ep_fn(
                2.0,
                int(seed),
                0,
                int(n_days),
                32,
                3,
                1,
                1,
                times,
                temps,
                **kwargs,
            )
        except TypeError:
            raw = ep_fn(int(seed), int(n_days), demand_profile_json, times, temps)
        return [int(x) for x in raw]

    cell_fn = getattr(core, "run_voi_crn_cell_py", None)
    if cell_fn is not None and "demand_profile_json" in inspect.signature(
        cell_fn
    ).parameters:
        pytest.fail(
            "run_voi_crn_cell_py accepts demand_profile_json but C4 needs "
            "run_voi_crn_episode_demands_py returning per-day physics demands"
        )

    pytest.fail(
        "T-121c C4 requires run_voi_crn_episode_demands_py or "
        "demand_profile_json kw on run_voi_crn_cell_py"
    )


# --- C1: μ(day) goldens vs Python ---


@pytest.mark.parametrize("day", _GOLDEN_DAYS)
def test_rust_demand_profile_mu_from_json_matches_python(day: int) -> None:
    profile = _committed_profile()
    expected = float(profile.mu(day))
    mu_fn = _require_demand_profile_mu_from_json_py()
    json_text = _profile_json_text()
    try:
        actual = float(mu_fn(json_text, int(day)))
    except TypeError:
        actual = float(mu_fn(str(_DEMAND_PROFILE_PATH), int(day)))
    assert actual == pytest.approx(expected, abs=_MU_ABS_TOL), (
        f"Rust μ({day})={actual} must match Python {expected} within {_MU_ABS_TOL}"
    )


# --- C3: 90-day rust-backend session with profile vs flat ---


def test_rust_backend_session_profile_mean_differs_from_flat_by_more_than_one() -> None:
    json_text = _profile_json_text()
    profile_mean = _rust_session_mean_demand(
        seed=_SESSION_SEED,
        n_days=_EPISODE_DAYS,
        demand_profile_json=json_text,
    )
    flat_mean = _rust_session_mean_demand(
        seed=_SESSION_SEED,
        n_days=_EPISODE_DAYS,
        demand_profile_json=None,
    )
    assert abs(profile_mean - flat_mean) > 1.0, (
        f"90-day profile mean {profile_mean:.4f} vs flat-session mean {flat_mean:.4f} "
        "must differ by >1.0 cases/day when calendar profile is configured (C3)"
    )
    assert abs(flat_mean - _FLAT_MU) <= 5.0, (
        f"flat-session mean {flat_mean:.4f} should stay near legacy demand_mu={_FLAT_MU}"
    )


# --- C4: VOI CRN episode demands profile vs flat ---


def test_voi_crn_episode_demands_profile_differs_from_flat() -> None:
    json_text = _profile_json_text()
    profile_demands = _voi_episode_demands(
        seed=_VOI_SEED,
        n_days=_EPISODE_DAYS,
        demand_profile_json=json_text,
    )
    flat_demands = _voi_episode_demands(
        seed=_VOI_SEED,
        n_days=_EPISODE_DAYS,
        demand_profile_json=None,
    )
    assert len(profile_demands) == _EPISODE_DAYS
    assert len(flat_demands) == _EPISODE_DAYS
    profile_mean = float(np.mean(profile_demands))
    flat_mean = float(np.mean(flat_demands))
    assert abs(profile_mean - flat_mean) > 1.0, (
        f"VOI 90-day profile mean {profile_mean:.4f} vs flat {flat_mean:.4f} "
        "must differ by >1.0 when demand_profile_json is wired (C4)"
    )
