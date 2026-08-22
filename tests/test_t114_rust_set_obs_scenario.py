"""T-114 RED: wasm worker + PyO3 session expose set_obs_scenario."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_wasm_worker_dispatches_set_obs_scenario() -> None:
    worker = REPO / "web" / "src" / "engine" / "wasmWorker.ts"
    text = worker.read_text(encoding="utf-8")
    assert "set_obs_scenario" in text
    assert "init" in text


def test_voi_core_session_mentions_set_obs_scenario() -> None:
    text = (REPO / "crates" / "voi_core" / "src" / "session.rs").read_text(
        encoding="utf-8"
    )
    assert "fn set_obs_scenario" in text
    assert '"set_obs_scenario"' in text


def test_pyo3_session_mentions_set_obs_scenario() -> None:
    text = (REPO / "crates" / "voi_py" / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "fn set_obs_scenario" in text
