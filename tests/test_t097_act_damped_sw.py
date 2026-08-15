"""T-097 EngineSession.act — damped_sw + SW-based rollout (RED).

Locks ``.team/specs/T-097.md`` and ADR 0117: ``damped_sw`` / ``sw`` aliases,
alpha/rho budget defaults and overrides, rollout base =
``DampedSurvivalWeightedPolicy`` (not ``ConstantOrderPolicy(0)``), constant
regression, unknown-policy error text.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.bakeoff_damped_sw import DampedSurvivalWeightedPolicy


@pytest.fixture(autouse=True)
def _rust_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBERRIES_VOI_BACKEND", "rust")


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DAY_DELTA_TOP_KEYS = frozenset({"seq", "episode_day", "day"})
_SESSION_MOD = "blueberries_voi.simulator.session"

_DEFAULT_ALPHA = 0.9
_DEFAULT_RHO = 0.8


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T097-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T097-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _minimal_config(**overrides: Any) -> dict[str, Any]:
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


def _new_session() -> Any:
    from blueberries_voi.simulator import EngineSession

    return EngineSession()


def _as_mapping(payload: Any, *, label: str) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    pytest.fail(f"{label} must be a Mapping/dict wire payload, got {type(payload)!r}")


def _assert_day_delta(payload: Any, *, label: str = "DayDelta") -> Mapping[str, Any]:
    delta = _as_mapping(payload, label=label)
    missing = _DAY_DELTA_TOP_KEYS - set(delta)
    assert not missing, f"{label} missing top-level keys {sorted(missing)}"
    assert isinstance(delta["seq"], int)
    assert isinstance(delta["episode_day"], int)
    assert isinstance(delta["day"], Mapping) or hasattr(delta["day"], "keys"), (
        f"{label}.day must be a single day object/mapping"
    )
    return delta


def _patch_damped_sw_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[float | None, float | None]]:
    """Record (alpha, rho) from every DampedSurvivalWeightedPolicy construction."""
    seen: list[tuple[float | None, float | None]] = []
    Real = DampedSurvivalWeightedPolicy

    class _SpyPolicy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            alpha = kwargs.get("alpha")
            if alpha is None and args:
                alpha = args[0]
            rho = kwargs.get("rho")
            seen.append(
                (
                    None if alpha is None else float(alpha),
                    None if rho is None else float(rho),
                )
            )
            super().__init__(*args, **kwargs)

    session_mod = importlib.import_module(_SESSION_MOD)
    monkeypatch.setitem(
        session_mod.EngineSession._select_order.__globals__,
        "DampedSurvivalWeightedPolicy",
        _SpyPolicy,
    )
    return seen


def _capture_rollout_base(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Replace session.rollout_order with a spy that records base_policy + budgets."""
    session_mod = importlib.import_module(_SESSION_MOD)
    captured: dict[str, Any] = {}
    real = session_mod.rollout_order

    def _spy(belief: Any, *args: Any, **kwargs: Any) -> int:
        captured["base_policy"] = kwargs.get("base_policy")
        captured["kwargs"] = dict(kwargs)
        if args:
            captured["args"] = args
        # Prefer real rollout when cheap dials are in place; fall back to 0.
        try:
            return int(real(belief, *args, **kwargs))
        except Exception:
            return 0

    monkeypatch.setitem(
        session_mod.EngineSession._select_order.__globals__,
        "rollout_order",
        _spy,
    )
    return captured


# ---------------------------------------------------------------------------
# AC: damped_sw / sw aliases return DayDelta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["damped_sw", "sw", "Damped_SW", "SW"])
def test_act_damped_sw_aliases_return_day_delta(policy: str) -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=97)
    delta = session.act(policy=policy)
    _assert_day_delta(delta, label=f"act({policy!r}) DayDelta")


# ---------------------------------------------------------------------------
# AC: alpha / rho defaults 0.9 / 0.8 and budget overrides
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="T-121 F3: _select_order removed; Rust owns policy dispatch")
def test_act_damped_sw_uses_default_alpha_0_9_and_rho_0_8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_damped_sw_spy(monkeypatch)
    session = _new_session()
    session.init(_minimal_config(), seed=11)
    session.act(policy="damped_sw")
    assert seen, "expected DampedSurvivalWeightedPolicy construction for damped_sw"
    alpha, rho = seen[-1]
    assert alpha == pytest.approx(_DEFAULT_ALPHA), (
        f"omitted alpha must default to {_DEFAULT_ALPHA}, got {alpha!r}"
    )
    assert rho == pytest.approx(_DEFAULT_RHO), (
        f"omitted rho must default to {_DEFAULT_RHO}, got {rho!r}"
    )


@pytest.mark.skip(reason="T-121 F3: _select_order removed; Rust owns policy dispatch")
def test_act_damped_sw_honours_alpha_rho_budget_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_damped_sw_spy(monkeypatch)
    session = _new_session()
    session.init(_minimal_config(), seed=12)
    session.act(policy="sw", alpha=0.75, rho=0.55)
    assert seen, "expected DampedSurvivalWeightedPolicy construction for sw"
    alpha, rho = seen[-1]
    assert alpha == pytest.approx(0.75)
    assert rho == pytest.approx(0.55)


@pytest.mark.skip(reason="T-121 F3: _select_order removed; Rust owns policy dispatch")
def test_act_rollout_base_uses_same_alpha_rho_defaults_and_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_damped_sw_spy(monkeypatch)
    captured = _capture_rollout_base(monkeypatch)
    session = _new_session()
    session.init(_minimal_config(H=2, n_rollout_paths=1), seed=13)

    session.act(policy="rollout", H=2, n_rollout_paths=1, candidate_case_radius=0)
    assert seen, "rollout base must construct DampedSurvivalWeightedPolicy"
    alpha0, rho0 = seen[-1]
    assert alpha0 == pytest.approx(_DEFAULT_ALPHA)
    assert rho0 == pytest.approx(_DEFAULT_RHO)
    base = captured.get("base_policy")
    assert isinstance(base, DampedSurvivalWeightedPolicy), (
        f"rollout base_policy must be DampedSurvivalWeightedPolicy, got {type(base)!r}"
    )

    seen.clear()
    session.act(
        policy="ctl",
        alpha=0.65,
        rho=0.4,
        H=2,
        n_rollout_paths=1,
        candidate_case_radius=0,
    )
    assert seen, "ctl alias must construct damped SW base with overrides"
    alpha1, rho1 = seen[-1]
    assert alpha1 == pytest.approx(0.65)
    assert rho1 == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# AC: rollout base is DampedSurvivalWeightedPolicy (not ConstantOrderPolicy(0))
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="T-121 F3: _select_order removed; Rust owns policy dispatch")
@pytest.mark.parametrize("policy", ["rollout", "ctl", "rollout_order"])
def test_act_rollout_base_policy_is_damped_sw_not_constant_zero(
    policy: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_rollout_base(monkeypatch)
    session = _new_session()
    session.init(_minimal_config(H=2, n_rollout_paths=1), seed=14)
    session.act(
        policy=policy,
        H=2,
        n_rollout_paths=1,
        candidate_case_radius=0,
        n_particles=16,
    )
    base = captured.get("base_policy")
    assert base is not None, f"act(policy={policy!r}) must call rollout_order"
    assert type(base).__name__ == "DampedSurvivalWeightedPolicy", (
        f"rollout base must be DampedSurvivalWeightedPolicy, got {type(base)!r}"
    )
    assert type(base).__name__ != "ConstantOrderPolicy", (
        "rollout must not wrap ConstantOrderPolicy(0) (ADR 0117 / T-097)"
    )


# ---------------------------------------------------------------------------
# AC: constant still works; unknown policy mentions damped_sw + rollout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("policy", "qty_key", "qty"),
    [
        ("constant", "order_qty", 8),
        ("const", "q", 4),
        ("fixed", "order_qty", 0),
    ],
)
def test_act_constant_aliases_still_honour_order_qty(
    policy: str, qty_key: str, qty: int
) -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=15)
    delta = session.act(policy=policy, **{qty_key: qty})
    _assert_day_delta(delta, label=f"act({policy!r}) DayDelta")


def test_act_unknown_policy_error_mentions_damped_sw_and_rollout() -> None:
    session = _new_session()
    session.init(_minimal_config(), seed=16)
    with pytest.raises(BaseException) as excinfo:
        session.act(policy="not_a_real_policy")
    msg = str(excinfo.value).lower()
    assert "damped_sw" in msg, (
        f"unknown policy error must mention damped_sw; got {excinfo.value!r}"
    )
    assert "rollout" in msg, (
        f"unknown policy error must mention rollout; got {excinfo.value!r}"
    )


@pytest.mark.skip(reason="T-121 F3: _select_order removed; Rust owns policy dispatch")
def test_act_budget_overrides_update_session_dials_and_rollout_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_rollout_base(monkeypatch)
    session = _new_session()
    session.init(
        _minimal_config(
            n_particles=32,
            H=3,
            n_rollout_paths=1,
            candidate_case_radius=1,
        ),
        seed=17,
    )
    session.act(
        policy="rollout",
        n_particles=24,
        H=2,
        n_rollout_paths=1,
        candidate_case_radius=0,
    )
    applied = session._applied_config()
    assert int(applied["n_particles"]) == 24
    assert int(applied["H"]) == 2
    assert int(applied["n_rollout_paths"]) == 1
    assert int(applied["candidate_case_radius"]) == 0
    kwargs = captured.get("kwargs") or {}
    assert int(kwargs.get("H", -1)) == 2
    assert int(kwargs.get("n_rollout_paths", -1)) == 1
    assert int(kwargs.get("candidate_case_radius", -1)) == 0
    assert int(kwargs.get("n_particles", -1)) == 24


# ---------------------------------------------------------------------------
# AC: worker / smoke policy allowlists must not stale-ban damped_sw
# ---------------------------------------------------------------------------


def test_worker_smoke_policy_surfaces_accept_damped_sw_when_listing_act_policies() -> (
    None
):
    """If packaging/worker smoke lists allowed act policies, include damped_sw.

    Also lock that session unknown-policy copy is not the stale
    \"constant or rollout\" exclusivity string once T-097 lands (asserted via
    act error text above). Here we scan packaging artifacts for allowlists.
    """
    roots = [
        _REPO_ROOT / "packaging" / "pyodide",
        _REPO_ROOT / "scripts",
    ]
    exclusive = re.compile(
        r"(constant\s+or\s+['\"]?rollout|only\s+(?:constant|rollout)"
        r"|allowed.*polic(?:y|ies).*(?:constant|rollout))",
        re.IGNORECASE,
    )
    stale_hits: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".js", ".md", ".ts", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if exclusive.search(text) and "damped_sw" not in text:
                stale_hits.append(path.relative_to(_REPO_ROOT).as_posix())
    # Session source currently has the stale message — that is the production
    # fix surface; flag it here so implement updates copy with the aliases.
    session_py = (
        _REPO_ROOT / "src" / "blueberries_voi" / "simulator" / "session.py"
    ).read_text(encoding="utf-8")
    if (
        "use 'constant' or 'rollout'" in session_py
        or 'use "constant" or "rollout"' in session_py
    ):
        stale_hits.append("src/blueberries_voi/simulator/session.py")
    assert not stale_hits, (
        "stale act policy allowlist / error copy must accept damped_sw "
        f"(T-097 / ADR 0117); offenders: {stale_hits}"
    )
