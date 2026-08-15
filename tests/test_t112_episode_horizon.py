"""T-112: studio episode horizon — full history, cap at day 90 (RED).

Locks `.team/specs/T-112.md` and ADR 0122. Python EngineSession never drops
thin-day history; step/act/step_n refuse at episode_day >= 90; Reset starts
a new episode. Rust/wasm is out of scope.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator import EngineSession

_EPISODE_HORIZON = 90


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T112-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T112-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "shipments": _fixture_shipments(),
        "n_particles": 8,
        "H": 2,
        "n_rollout_paths": 1,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": False,
    }
    cfg.update(overrides)
    return cfg


def _history(session: EngineSession) -> list[dict[str, Any]]:
    snap = session._snapshot()
    raw = snap["history"]
    assert isinstance(raw, list)
    return raw


def _episode_day(session: EngineSession) -> int:
    return int(session._snapshot()["episode_day"])


def test_history_keeps_all_days_past_former_14_day_window() -> None:
    session = EngineSession()
    session.init(_config(), seed=1)
    n = 16
    for _ in range(n):
        delta = session.step(0)
        assert "drop_oldest" in delta
        assert delta["drop_oldest"] is False
    history = _history(session)
    assert len(history) == n
    assert [int(d["day"]) for d in history] == list(range(n))
    assert _episode_day(session) == n


def test_default_backend_does_not_pop_old_thin_days() -> None:
    """Default Python session (filter on, small demo N) still keeps >14 days."""
    session = EngineSession()
    session.init(_config(enable_filter=True, n_particles=16), seed=2)
    for _ in range(15):
        delta = session.step(0)
        assert delta["drop_oldest"] is False
    history = _history(session)
    assert len(history) == 15
    assert int(history[0]["day"]) == 0
    assert int(history[-1]["day"]) == 14


def test_step_refuses_at_episode_day_90_with_reset_message() -> None:
    session = EngineSession()
    session.init(_config(), seed=4)
    session.step_n([0] * _EPISODE_HORIZON)
    assert _episode_day(session) == _EPISODE_HORIZON
    with pytest.raises(ValueError, match=r"(?i)(episode|horizon).*(reset)|reset"):
        session.step(0)


def test_act_refuses_at_episode_day_90() -> None:
    session = EngineSession()
    session.init(_config(), seed=5)
    session.step_n([0] * _EPISODE_HORIZON)
    with pytest.raises(ValueError, match=r"(?i)reset"):
        session.act(policy="constant", order_qty=0)


def test_step_n_crossing_cap_refuses_without_partial_prefix() -> None:
    session = EngineSession()
    session.init(_config(), seed=6)
    session.step_n([0] * (_EPISODE_HORIZON - 1))
    assert _episode_day(session) == _EPISODE_HORIZON - 1
    hist_len = len(_history(session))
    seq = int(session._snapshot()["seq"])
    with pytest.raises(ValueError, match=r"(?i)reset"):
        session.step_n([0, 0])
    assert _episode_day(session) == _EPISODE_HORIZON - 1
    assert len(_history(session)) == hist_len
    assert int(session._snapshot()["seq"]) == seq


def test_step_allowed_on_day_89_then_refuses_at_90() -> None:
    session = EngineSession()
    session.init(_config(), seed=7)
    session.step_n([0] * (_EPISODE_HORIZON - 1))
    delta = session.step(0)
    assert delta["drop_oldest"] is False
    assert _episode_day(session) == _EPISODE_HORIZON
    with pytest.raises(ValueError, match=r"(?i)reset"):
        session.step(0)


def test_reset_clears_history_and_allows_new_episode_from_day_0() -> None:
    session = EngineSession()
    session.init(_config(), seed=8)
    session.step_n([0] * _EPISODE_HORIZON)
    with pytest.raises(ValueError):
        session.step(0)
    snap = session.reset(_config(), seed=8)
    assert snap["episode_day"] == 0
    assert snap["history"] == []
    delta = session.step(0)
    assert delta["drop_oldest"] is False
    assert _episode_day(session) == 1
    assert len(_history(session)) == 1


def test_init_clears_history_like_reset() -> None:
    session = EngineSession()
    session.init(_config(), seed=9)
    session.step_n([0] * 20)
    snap = session.init(_config(), seed=9)
    assert snap["episode_day"] == 0
    assert snap["history"] == []


def test_mock_adapter_source_refuses_at_day_90_like_python_session() -> None:
    """JS mock host must hard-stop at the same 90-day cap as EngineSession."""
    src = (
        Path(__file__).resolve().parents[1] / "web" / "src" / "mock" / "adapter.ts"
    ).read_text(encoding="utf-8")
    assert "episode ended" in src
    assert "Reset" in src
    assert "90" in src
