"""T-042: unify case_round to nearest / half-away-from-zero (audit remediation).

Locks controller.ordering.case_round as the sole semantic; sim.episode must not
keep ceil-to-case; closed-loop orders use nearest. See `.team/specs/T-042.md`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

from blueberries_voi.controller.ordering import case_round as controller_case_round
from blueberries_voi.model import ModelParams
from blueberries_voi.model.abdella import ShipmentTrace

if TYPE_CHECKING:
    from collections.abc import Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EPISODE_PATH = _REPO_ROOT / "src" / "blueberries_voi" / "sim" / "episode.py"

# Midpoints / nearest fixtures from T-026 / T-042 (case_size=8).
_NEAREST_MIDPOINTS: tuple[tuple[float, int], ...] = (
    (4.0, 8),
    (12.0, 16),
)
# Where ceil and nearest disagree: nearest → 8, ceil → 16.
_DISAGREE_X = 9.0
_DISAGREE_CASE = 8
_DISAGREE_NEAREST = 8


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T042-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        )
    ]


def _resolve_sim_case_round() -> Any:
    """Public sim.episode.case_round (or sim.case_round re-export)."""
    for mod_name in ("blueberries_voi.sim.episode", "blueberries_voi.sim"):
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, "case_round", None)
        if callable(fn):
            return fn
    pytest.fail("missing public case_round under blueberries_voi.sim.episode / sim")


class _RawQtyPolicy:
    """Policy that always returns a fixed raw quantity (pre case_round)."""

    def __init__(self, raw: int) -> None:
        self.raw = int(raw)

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
    ) -> int:
        del day, belief, pending_orders
        return self.raw


# ---------------------------------------------------------------------------
# AC: controller.ordering.case_round remains nearest / half-away-from-zero
# ---------------------------------------------------------------------------


def test_controller_case_round_midpoints_half_away_from_zero() -> None:
    """Fixture: x=4 → 8; x=12 → 16 under case_size=8 (T-042 / T-026)."""
    for x, expected in _NEAREST_MIDPOINTS:
        assert controller_case_round(x, 8) == expected


def test_controller_case_round_non_midpoints_match_nearest() -> None:
    assert controller_case_round(3.9, 8) == 0
    assert controller_case_round(4.1, 8) == 8
    assert controller_case_round(11.9, 8) == 8
    assert controller_case_round(12.1, 8) == 16


# ---------------------------------------------------------------------------
# AC: sim.episode has no ceil-to-case; public case_round matches controller
# ---------------------------------------------------------------------------


def test_sim_episode_case_round_source_has_no_ceil_arithmetic() -> None:
    """No np.ceil (or equivalent ceil-to-case) in the episode case_round path."""
    assert _EPISODE_PATH.is_file()
    source = _EPISODE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    case_round_fn: ast.FunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "case_round":
            case_round_fn = node
            break
    # Thin re-export (no local def) is OK — then the body must not exist here.
    if case_round_fn is None:
        assert (
            "from blueberries_voi.controller.ordering import case_round" in source
            or ("controller.ordering" in source and "case_round" in source)
        ), "sim.episode must re-export controller case_round or define a thin wrapper"
        return

    body_src = ast.get_source_segment(source, case_round_fn) or ""
    assert "np.ceil" not in body_src and "ceil(" not in body_src, (
        "sim.episode.case_round must not implement ceil-to-case "
        f"(found ceil in:\n{body_src})"
    )
    # Equivalent ceil-to-case: math.ceil / numpy.ceil attribute use
    for walk_node in ast.walk(case_round_fn):
        if isinstance(walk_node, ast.Attribute) and walk_node.attr == "ceil":
            pytest.fail("sim.episode.case_round must not call *.ceil")
        if isinstance(walk_node, ast.Name) and walk_node.id == "ceil":
            pytest.fail("sim.episode.case_round must not reference ceil")


def test_sim_case_round_matches_controller_on_shared_inputs() -> None:
    sim_round = _resolve_sim_case_round()
    samples = (0.0, 4.0, 8.0, 9.0, 12.0, 15.0, 16.0)
    for x in samples:
        ctrl = controller_case_round(float(x), _DISAGREE_CASE)
        got = sim_round(x, _DISAGREE_CASE)
        assert int(got) == ctrl, (
            f"sim.case_round({x}, {_DISAGREE_CASE})={got} != controller {ctrl}"
        )


def test_sim_and_controller_agree_where_ceil_and_nearest_disagree() -> None:
    """x=9, case_size=8: nearest → 8 (ceil would be 16)."""
    sim_round = _resolve_sim_case_round()
    assert controller_case_round(_DISAGREE_X, _DISAGREE_CASE) == _DISAGREE_NEAREST
    assert int(sim_round(_DISAGREE_X, _DISAGREE_CASE)) == _DISAGREE_NEAREST


# ---------------------------------------------------------------------------
# AC: run_closed_loop_episode uses nearest (not ceil) on disagreeing band
# ---------------------------------------------------------------------------


def test_closed_loop_orders_use_nearest_not_ceil_on_disagree_band() -> None:
    from blueberries_voi.sim.episode import run_closed_loop_episode

    raw = int(_DISAGREE_X)  # 9
    policy = _RawQtyPolicy(raw)
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=_DISAGREE_CASE),
        n_burn=1,
        n_score=3,
        root_seed=42,
        run_id="t042-nearest",
    )
    assert ep.scored, "expected scored days"
    for day in ep.scored:
        assert day.order_qty == _DISAGREE_NEAREST, (
            f"closed-loop order_qty={day.order_qty} for raw={raw}; "
            f"expected nearest {_DISAGREE_NEAREST} (ceil would be 16)"
        )
        assert day.order_qty % _DISAGREE_CASE == 0


def test_closed_loop_midpoint_matches_controller_half_away() -> None:
    from blueberries_voi.sim.episode import run_closed_loop_episode

    # raw 4 → nearest 8 (half-away); ceil would also be 8 — still locks wiring.
    policy = _RawQtyPolicy(4)
    ep = run_closed_loop_episode(
        policy,
        shipments=_fixture_shipments(),
        params=ModelParams(case_size=8),
        n_burn=1,
        n_score=2,
        root_seed=7,
        run_id="t042-mid",
    )
    for day in ep.scored:
        assert day.order_qty == 8


def test_t026_controller_fixtures_still_exported() -> None:
    """T-026 nearest fixtures remain the controller contract (suite must stay green)."""
    assert controller_case_round(4.0, 8) == 8
    assert controller_case_round(12.0, 8) == 16
    # Ordering module still documents nearest (pre-existing T-026 surface).
    mod = importlib.import_module("blueberries_voi.controller.ordering")
    assert "nearest" in (mod.__doc__ or "").lower()
    sig = inspect.signature(controller_case_round)
    assert "case_size" in sig.parameters
