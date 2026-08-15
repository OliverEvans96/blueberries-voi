"""T-121c Wave C: Rust calendar demand (CAL-01) — RED contracts (C1, C3).

With ``BLUEBERRIES_VOI_BACKEND=rust`` and ``blueberries_voi._core`` built:

* ``DemandProfile::mu(day)`` matches Python ``DemandProfile.mu(day)`` on golden days
* a fixed-seed 90-day session records demand whose mean tracks the FreshNet
  calendar profile — not a flat μ=30 baseline (by >1.0 cases/day vs that baseline)
"""

from __future__ import annotations

import importlib
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model import ModelParams, draw_demand
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.model.demand_profile import DemandProfile, load_demand_profile
from blueberries_voi.rng import STREAM_DEMAND, spawn_rng
from blueberries_voi.simulator.session import EPISODE_HORIZON, EngineSession

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMAND_PROFILE_PATH = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_MU_ABS_TOL = 1e-9
_FLAT_MU = 30.0
_MEAN_DIFF_MIN = 1.0
_GOLDEN_DAYS = (0, 6, 7, 13, 89)
_SESSION_SEED = 0


@pytest.fixture(autouse=True)
def rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def _committed_profile() -> DemandProfile:
    assert _DEMAND_PROFILE_PATH.is_file(), (
        "committed data/freshnet/demand_profile.json required (T-080 / T-121c)"
    )
    return load_demand_profile(_DEMAND_PROFILE_PATH)


def _rust_demand_profile_mu(day: int) -> float:
    """Resolve Rust μ(day) from the committed FreshNet JSON (C1 surface)."""
    for name in (
        "demand_profile_mu_py",
        "demand_profile_mu_from_json_py",
        "freshnet_mu_py",
    ):
        fn = getattr(_maybe_core, name, None)
        if callable(fn):
            try:
                return float(fn(int(day), str(_DEMAND_PROFILE_PATH)))
            except TypeError:
                return float(fn(int(day)))
    cls = getattr(_maybe_core, "DemandProfile", None)
    if cls is not None:
        loader = getattr(cls, "from_json", None)
        mu_fn = getattr(cls, "mu", None)
        if callable(loader) and callable(mu_fn):
            profile = loader(str(_DEMAND_PROFILE_PATH))
            return float(mu_fn(profile, int(day)))
    pytest.fail(
        "Rust DemandProfile μ(day) not exposed via PyO3 "
        "(expected demand_profile_mu_py or DemandProfile.from_json + mu; T-121 C1)"
    )


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


def _session_cfg(*, enable_filter: bool = False) -> dict[str, Any]:
    return {
        "shipments": _ships(),
        "n_particles": 16,
        "H": 3,
        "n_rollout_paths": 1,
        "candidate_case_radius": 0,
        "L": 2,
        "K": 4,
        "enable_filter": enable_filter,
    }


def _rust_session_demands(*, seed: int, days: int) -> list[int]:
    session = EngineSession()
    session.init(_session_cfg(), seed=seed)
    out: list[int] = []
    for _ in range(days):
        delta = session.step(0)
        out.append(int(delta["day"]["demand"]))
    return out


def _python_calendar_demands(*, seed: int, days: int) -> list[int]:
    """Reference calendar demand draws (Python profile + addressed demand stream)."""
    profile = _committed_profile()
    params = ModelParams(demand_profile=profile, demand_mu=_FLAT_MU)
    out: list[int] = []
    for day in range(days):
        rng = spawn_rng(seed, run_id="session", day=day, stream=STREAM_DEMAND)
        out.append(int(draw_demand(rng, params, day=day)))
    return out


def _calendar_mu_mean(days: int) -> float:
    profile = _committed_profile()
    return float(statistics.mean(profile.mu(day) for day in range(days)))


@pytest.mark.parametrize("day", _GOLDEN_DAYS)
def test_rust_demand_profile_mu_matches_python_golden(day: int) -> None:
    """C1: Rust μ(day) equals Python DemandProfile within 1e-9."""
    py_mu = _committed_profile().mu(day)
    rust_mu = _rust_demand_profile_mu(day)
    assert math.isclose(rust_mu, py_mu, rel_tol=0.0, abs_tol=_MU_ABS_TOL), (
        f"Rust μ({day})={rust_mu} must match Python {py_mu} "
        f"(|Δ| ≤ {_MU_ABS_TOL})"
    )


def test_rust_90day_session_mean_demand_tracks_calendar_not_flat_mu() -> None:
    """C3: 90-day rust session demand mean follows FreshNet calendar, not flat μ=30."""
    days = EPISODE_HORIZON
    calendar_ref = _python_calendar_demands(seed=_SESSION_SEED, days=days)
    ref_mean = float(statistics.mean(calendar_ref))
    rust_demands = _rust_session_demands(seed=_SESSION_SEED, days=days)
    rust_mean = float(statistics.mean(rust_demands))

    assert abs(ref_mean - _FLAT_MU) > _MEAN_DIFF_MIN, (
        f"fixture seed {_SESSION_SEED} must separate calendar from flat μ={_FLAT_MU} "
        f"(reference mean={ref_mean})"
    )
    assert abs(_calendar_mu_mean(days) - _FLAT_MU) > 0.05, (
        "committed profile mean μ(day) over 90 days must not be exactly flat 30"
    )
    assert abs(rust_mean - ref_mean) <= 1.0, (
        "Rust session demand mean must track calendar reference when profile is "
        f"loaded (rust={rust_mean}, calendar ref={ref_mean}); flat μ=30 baseline "
        f"is {_FLAT_MU}"
    )
