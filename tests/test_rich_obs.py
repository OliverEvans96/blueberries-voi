"""T-010 RichObs + UNOBSERVED + scenario masks (RED / acceptance)."""

from __future__ import annotations

import dataclasses
from datetime import date
from types import SimpleNamespace
from typing import Any, Union, get_args, get_origin, get_type_hints

import numpy as np
import pytest

from typing import Any as RBPF  # T-121 F3
from blueberries_voi.filter import types as filter_types
from blueberries_voi.model import ModelParams

# ADR 0086 present-field table (✓ only; "weak" not required present).
_REQUIRED_PRESENT: dict[str, frozenset[str]] = {
    "P0": frozenset({"arrivals", "sales_total"}),
    "P1": frozenset({"arrivals", "sales_total", "waste_total"}),
    "F1": frozenset(
        {"arrivals", "sales_total", "waste_total", "sales_by_lot", "lot_ids_live"}
    ),
    "F1s": frozenset(
        {"arrivals", "sales_total", "waste_total", "waste_by_lot", "lot_ids_live"}
    ),
    "F2a": frozenset({"arrivals", "sales_total", "waste_total", "pack_date"}),
    "F2": frozenset(
        {
            "arrivals",
            "sales_total",
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "age_at_receipt",
            "lot_ids_live",
        }
    ),
}

_ALWAYS_ABSENT: dict[str, frozenset[str]] = {
    "P0": frozenset(
        {
            "waste_total",
            "sales_by_lot",
            "waste_by_lot",
            "pack_date",
            "age_at_receipt",
        }
    ),
    "P1": frozenset(
        {
            "sales_by_lot",
            "waste_by_lot",
            "pack_date",
            "age_at_receipt",
        }
    ),
    "F1": frozenset({"waste_by_lot", "pack_date", "age_at_receipt"}),
    "F1s": frozenset({"sales_by_lot", "pack_date", "age_at_receipt"}),
    "F2a": frozenset(
        {
            "sales_by_lot",
            "waste_by_lot",
            "age_at_receipt",
        }
    ),
    "F2": frozenset({"pack_date"}),  # subsumed by age_at_receipt per ADR
}

_RICH_FIELD_NAMES = (
    "arrivals",
    "sales_total",
    "waste_total",
    "sales_by_lot",
    "waste_by_lot",
    "pack_date",
    "age_at_receipt",
    "lot_ids_live",
)


def _require(name: str) -> Any:
    """Fetch a T-010 symbol from filter.types; fail (not error) if missing."""
    assert hasattr(filter_types, name), f"filter.types missing {name!r} (T-010)"
    return getattr(filter_types, name)


def _full_rich_obs(*, waste_total: int = 0) -> Any:
    """Fully observed RichObs (all fields concrete, including zeros/empties)."""
    rich_obs_cls = _require("RichObs")
    return rich_obs_cls(
        arrivals=8,
        sales_total=10,
        waste_total=waste_total,
        sales_by_lot={1: 10},
        waste_by_lot={2: waste_total} if waste_total else {},
        pack_date=date(2024, 3, 1),
        age_at_receipt=2.5,
        lot_ids_live=frozenset({1, 2}),
    )


def _type_includes(annotation: object, expected: type) -> bool:
    """True if ``annotation`` is ``expected`` or a Union/Optional containing it."""
    if annotation is expected:
        return True
    origin = get_origin(annotation)
    if origin is Union:
        return any(_type_includes(arg, expected) for arg in get_args(annotation))
    union_type = getattr(__import__("types"), "UnionType", None)
    if union_type is not None and origin is union_type:
        return any(_type_includes(arg, expected) for arg in get_args(annotation))
    return False


def _day_log_like(**overrides: Any) -> SimpleNamespace:
    """Minimal DayLog-shaped object matching T-009 rich emit interface."""
    base: dict[str, Any] = {
        "day": 3,
        "lots": [
            SimpleNamespace(n=5, tau=1.0, lot_id=1),
            SimpleNamespace(n=3, tau=2.0, lot_id=2),
        ],
        "sales_total": 10,
        "waste_total": 0,
        "arrivals": 8,
        "order_qty": 8,
        "demand": 12,
        "L": 2,
        "sales_by_lot": {1: 7, 2: 3},
        "waste_by_lot": {},
        "age_at_receipt": 2.5,
        "pack_date": date(2024, 3, 1),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# AC1: RichObs frozen dataclass with required fields
# ---------------------------------------------------------------------------


def test_rich_obs_is_frozen_dataclass_with_required_fields() -> None:
    rich_obs_cls = _require("RichObs")
    assert dataclasses.is_dataclass(rich_obs_cls)
    field_names = {f.name for f in dataclasses.fields(rich_obs_cls)}
    for name in _RICH_FIELD_NAMES:
        assert name in field_names, f"RichObs missing field {name!r}"

    obs = _full_rich_obs(waste_total=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.waste_total = 99
    # replace returns a new instance; mutation of the original must still fail
    replaced = dataclasses.replace(obs, waste_total=99)
    assert replaced.waste_total == 99
    assert obs.waste_total == 1


# ---------------------------------------------------------------------------
# AC2: UNOBSERVED sentinel distinct from 0, None, {}
# ---------------------------------------------------------------------------


def test_unobserved_sentinel_distinct_from_zero_none_empty() -> None:
    unobserved = _require("UNOBSERVED")
    is_unobserved = _require("is_unobserved")
    assert unobserved is not None
    assert unobserved != 0
    assert unobserved != {}
    empty: dict[int, int] = {}
    assert unobserved != empty
    assert is_unobserved(unobserved) is True
    assert is_unobserved(0) is False
    assert is_unobserved(None) is False
    assert is_unobserved({}) is False
    assert is_unobserved(0.0) is False


# ---------------------------------------------------------------------------
# AC3: ObsMask.apply sets absent fields to UNOBSERVED, never 0 / {}
# ---------------------------------------------------------------------------


def test_obs_mask_apply_sets_absent_fields_to_unobserved_never_zero_or_empty() -> None:
    unobserved = _require("UNOBSERVED")
    is_unobserved = _require("is_unobserved")
    obs_mask_cls = _require("ObsMask")
    rich = _full_rich_obs(waste_total=0)
    mask = obs_mask_cls(present=frozenset({"arrivals", "sales_total"}))
    masked = mask.apply(rich)

    assert masked.arrivals == 8
    assert masked.sales_total == 10
    assert masked.waste_total is unobserved
    assert masked.sales_by_lot is unobserved
    assert masked.waste_by_lot is unobserved
    assert masked.pack_date is unobserved
    assert masked.age_at_receipt is unobserved
    assert masked.lot_ids_live is unobserved

    assert masked.waste_total != 0
    assert masked.sales_by_lot != {}
    assert masked.waste_by_lot != {}
    assert is_unobserved(masked.waste_total)
    assert is_unobserved(masked.sales_by_lot)


# ---------------------------------------------------------------------------
# AC4: mask_for covers P0..F2; P0 hides waste_total, P1 presents it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["P0", "P1", "F1", "F1s", "F2a", "F2"])
def test_mask_for_covers_scenario_present_and_absent_fields(scenario: str) -> None:
    unobserved = _require("UNOBSERVED")
    is_unobserved = _require("is_unobserved")
    obs_mask_cls = _require("ObsMask")
    mask_for = _require("mask_for")

    mask = mask_for(scenario)
    assert isinstance(mask, obs_mask_cls)
    required = _REQUIRED_PRESENT[scenario]
    absent = _ALWAYS_ABSENT[scenario]
    assert required <= mask.present
    assert mask.present.isdisjoint(absent)

    rich = _full_rich_obs(waste_total=0)
    masked = mask.apply(rich)
    for name in required:
        assert getattr(masked, name) is not unobserved
        assert not is_unobserved(getattr(masked, name))
    for name in absent:
        assert getattr(masked, name) is unobserved
        assert is_unobserved(getattr(masked, name))


def test_mask_for_p0_hides_waste_total_p1_presents_it() -> None:
    mask_for = _require("mask_for")
    p0 = mask_for("P0")
    p1 = mask_for("P1")
    assert "waste_total" not in p0.present
    assert "waste_total" in p1.present
    assert {"arrivals", "sales_total"} <= p0.present
    assert {"arrivals", "sales_total"} <= p1.present


# ---------------------------------------------------------------------------
# AC5: waste_total=0 + P0 mask → UNOBSERVED not 0
# ---------------------------------------------------------------------------


def test_p0_mask_turns_observed_zero_waste_into_unobserved() -> None:
    unobserved = _require("UNOBSERVED")
    is_unobserved = _require("is_unobserved")
    mask_for = _require("mask_for")
    rich = _full_rich_obs(waste_total=0)
    assert rich.waste_total == 0
    masked = mask_for("P0").apply(rich)
    assert masked.waste_total is unobserved
    assert masked.waste_total != 0
    assert is_unobserved(masked.waste_total)


# ---------------------------------------------------------------------------
# AC6: rich_obs_from_day_log projects through mask without inventing hidden fields
# ---------------------------------------------------------------------------


def test_rich_obs_from_day_log_projects_through_mask_without_inventing() -> None:
    unobserved = _require("UNOBSERVED")
    mask_for = _require("mask_for")
    rich_obs_from_day_log = _require("rich_obs_from_day_log")
    day = _day_log_like(waste_total=0, waste_by_lot={})

    p0_obs = rich_obs_from_day_log(day, mask_for("P0"))
    assert p0_obs.arrivals == 8
    assert p0_obs.sales_total == 10
    assert p0_obs.waste_total is unobserved
    assert p0_obs.sales_by_lot is unobserved
    assert p0_obs.waste_by_lot is unobserved
    assert p0_obs.pack_date is unobserved
    assert p0_obs.age_at_receipt is unobserved

    f1_obs = rich_obs_from_day_log(day, mask_for("F1"))
    assert f1_obs.sales_by_lot == {1: 7, 2: 3}
    assert f1_obs.waste_total == 0
    assert f1_obs.waste_by_lot is unobserved
    assert f1_obs.pack_date is unobserved
    assert f1_obs.lot_ids_live == frozenset({1, 2})

    f2a_obs = rich_obs_from_day_log(day, mask_for("F2a"))
    assert f2a_obs.pack_date == date(2024, 3, 1)
    assert f2a_obs.sales_by_lot is unobserved
    assert f2a_obs.age_at_receipt is unobserved


def test_rich_obs_from_day_log_does_not_invent_missing_delivery_metadata() -> None:
    unobserved = _require("UNOBSERVED")
    mask_for = _require("mask_for")
    rich_obs_from_day_log = _require("rich_obs_from_day_log")
    day = _day_log_like(
        arrivals=0,
        age_at_receipt=None,
        pack_date=None,
        sales_by_lot={1: 10},
        waste_by_lot={},
    )
    # Under F2, age_at_receipt is masked-present but day has None — must not invent 0.0.
    f2_obs = rich_obs_from_day_log(day, mask_for("F2"))
    assert f2_obs.age_at_receipt is unobserved or f2_obs.age_at_receipt is None
    assert f2_obs.age_at_receipt != 0
    assert f2_obs.age_at_receipt != 0.0


# ---------------------------------------------------------------------------
# AC7: RBPF.step accepts RichObs (type boundary)
# ---------------------------------------------------------------------------


def test_rbpf_step_type_boundary_accepts_rich_obs() -> None:
    rich_obs_cls = _require("RichObs")
    mask_for = _require("mask_for")
    hints = get_type_hints(RBPF.step)
    assert "obs" in hints
    assert _type_includes(hints["obs"], rich_obs_cls), (
        f"RBPF.step obs annotation must accept RichObs; got {hints['obs']!r}"
    )

    rbpf = RBPF(params=ModelParams(), N=20, K=4, L=2)
    rng = np.random.default_rng(0)
    rbpf.initialize(rng)
    obs = mask_for("P1").apply(_full_rich_obs(waste_total=1))
    summary = rbpf.step(obs, rng)
    assert summary.ess > 0


# ---------------------------------------------------------------------------
# AC8: B-state is not a fabricating observation mask
# ---------------------------------------------------------------------------


def test_mask_for_rejects_b_state_scenario() -> None:
    """SCN-B-state is a bypass, not a fabricating ObsMask."""
    mask_for = _require("mask_for")
    with pytest.raises((ValueError, KeyError, TypeError)):
        mask_for("B-state")
