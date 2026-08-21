"""T-121b Wave B: Rust policy engine ``act`` - RED contracts (B2-B4).

With ``BLUEBERRIES_VOI_BACKEND=rust`` and ``blueberries_voi._core`` built,
``EngineSession.act`` must dispatch constant / damped_sw / rollout on belief
counts (not ground-truth shelf state) and honor budget kwargs.
"""

from __future__ import annotations

import importlib
import inspect
import os
from typing import Any

import numpy as np
import pytest

from blueberries_voi.backend import rust_core as _maybe_core
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.session import EngineSession

if _maybe_core is None:
    pytest.skip("blueberries_voi._core not built", allow_module_level=True)

rust_core = _maybe_core

# Tier 2 deferral: Rust/Python belief-mean RNG paths are structurally equivalent
# but not bit-identical (ADR 0127). These parity tests stay xfail until Tier 2.
_BELIEF_RNG_XFAIL = pytest.mark.xfail(
    strict=False,
    reason="T-121 Tier 2: structural belief RNG parity deferred per ADR 0127",
)

CASE_SIZE = int(ModelParams().case_size)
_WARM_STEPS = 6
_SEED = 99
_CONSTANT_Q = 16


@pytest.fixture(autouse=True)
def rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force rust backend for every test in this module."""
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)


def _ships() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T121b",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _session_cfg(*, enable_filter: bool = True) -> dict[str, Any]:
    return {
        "shipments": _ships(),
        "n_particles": 32,
        "H": 7,
        "n_rollout_paths": 2,
        "candidate_case_radius": 1,
        "L": 2,
        "K": 4,
        "enable_filter": enable_filter,
    }


def _policy_order(
    policy: str,
    *,
    backend: str,
    seed: int = _SEED,
    warm_steps: int = _WARM_STEPS,
    enable_filter: bool = True,
    order_qty: int = _CONSTANT_Q,
) -> int:
    os.environ["BLUEBERRIES_VOI_BACKEND"] = backend
    import blueberries_voi.backend as backend_mod

    importlib.reload(backend_mod)

    session = EngineSession()
    session.init(_session_cfg(enable_filter=enable_filter), seed=seed)
    for _ in range(warm_steps):
        session.step(0)
    if policy in {"constant", "const", "fixed"}:
        delta = session.act(policy=policy, order_qty=order_qty)
    else:
        delta = session.act(policy=policy)
    return int(delta["day"]["order_qty"])


def _rust_act_accepts_constant_kwargs() -> bool:
    sig = inspect.signature(rust_core.PyEngineSession.act)
    names = set(sig.parameters)
    return bool({"order_qty", "q"} & names)


def _require_constant_kwargs_wired() -> None:
    if not _rust_act_accepts_constant_kwargs():
        pytest.fail(
            "PyEngineSession.act must accept order_qty or q for constant policy "
            "(T-121 B4)"
        )


def _assert_case_multiple(order_qty: int, *, policy: str) -> None:
    assert order_qty >= 0, f"{policy} order must be non-negative, got {order_qty}"
    if order_qty:
        assert order_qty % CASE_SIZE == 0, (
            f"{policy} order {order_qty} must be a multiple of case_size={CASE_SIZE}"
        )


# AC B4: budget kwargs routed through PyO3 act
def test_rust_pyo3_act_accepts_constant_order_qty_kwarg() -> None:
    _require_constant_kwargs_wired()


# AC B2/B4: constant policy returns case-multiples
def test_constant_policy_returns_case_multiple_on_order_day() -> None:
    _require_constant_kwargs_wired()
    order_qty = _policy_order("constant", backend="rust")
    _assert_case_multiple(order_qty, policy="constant")
    assert order_qty == _CONSTANT_Q


# AC B3: damped_sw returns case-multiples from belief
def test_damped_sw_policy_returns_case_multiple() -> None:
    order_qty = _policy_order("damped_sw", backend="rust")
    _assert_case_multiple(order_qty, policy="damped_sw")


# AC B3: rollout returns case-multiples from belief
def test_rollout_policy_returns_case_multiple() -> None:
    order_qty = _policy_order("rollout", backend="rust")
    _assert_case_multiple(order_qty, policy="rollout")


# AC B3: damped_sw uses belief (structural parity vs Python reference)
@_BELIEF_RNG_XFAIL
def test_damped_sw_matches_python_belief_reference() -> None:
    py_order = _policy_order("damped_sw", backend="python")
    rust_order = _policy_order("damped_sw", backend="rust")
    _assert_case_multiple(rust_order, policy="damped_sw")
    assert rust_order == py_order, (
        "Rust damped_sw must order from belief mean, not ground-truth counts "
        f"(rust={rust_order}, python belief reference={py_order})"
    )


# AC B3: rollout uses belief (structural parity vs Python reference)
@_BELIEF_RNG_XFAIL
def test_rollout_matches_python_belief_reference() -> None:
    py_order = _policy_order("rollout", backend="python")
    rust_order = _policy_order("rollout", backend="rust")
    _assert_case_multiple(rust_order, policy="rollout")
    assert rust_order == py_order, (
        "Rust rollout must order from belief mean, not ground-truth counts "
        f"(rust={rust_order}, python belief reference={py_order})"
    )


# AC B3: rollout differs from trivial constant when filter enabled
@_BELIEF_RNG_XFAIL
def test_rollout_differs_from_constant_when_filter_enabled() -> None:
    _require_constant_kwargs_wired()
    const_order = _policy_order("constant", backend="rust")
    roll_order = _policy_order("rollout", backend="rust")
    _assert_case_multiple(const_order, policy="constant")
    _assert_case_multiple(roll_order, policy="rollout")
    assert const_order == _CONSTANT_Q
    assert roll_order != const_order, (
        "With filter enabled and nontrivial belief, rollout must differ from "
        f"constant q={_CONSTANT_Q} (rollout={roll_order})"
    )


# AC B3: distinct policy dispatch (damped_sw vs rollout)
@_BELIEF_RNG_XFAIL
def test_damped_sw_and_rollout_are_distinct_when_reference_differs() -> None:
    rust_sw = _policy_order("damped_sw", backend="rust")
    rust_roll = _policy_order("rollout", backend="rust")
    assert rust_sw != rust_roll, (
        f"Rust must dispatch damped_sw and rollout separately (both returned {rust_sw})"
    )
