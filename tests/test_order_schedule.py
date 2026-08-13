"""T-077: OrderSchedule API (CAL-A1) — failing tests before implementation.

Locks ADR 0111 / 0109 / ``.team/specs/T-077.md``:

* frozen ``OrderSchedule`` with MWF delivery, LT=1, Sun/Tue/Thu order defaults
* ``can_order`` / ``next_order_day`` / ``protection_days`` (3/3/4)
* epoch day 0 = Monday 2024-01-01
* no HF / ``datasets`` / web imports on the public path
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

# ADR 0111: under sim/ (preferred) or controller/ (Track A).
_MODULE_CANDIDATES = (
    "blueberries_voi.sim.order_schedule",
    "blueberries_voi.controller.order_schedule",
)

_PACKAGE_EXPORT_CANDIDATES = (
    "blueberries_voi.sim",
    "blueberries_voi.controller",
)

_EPOCH = date(2024, 1, 1)
_DEFAULT_DELIVERY = frozenset({0, 2, 4})  # Mon / Wed / Fri
_DEFAULT_ORDER = frozenset({6, 1, 3})  # Sun / Tue / Thu
_DEFAULT_LEAD_TIME = 1

# HuggingFace / web surfaces must stay off the OrderSchedule import path.
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "datasets",
        "huggingface_hub",
        "huggingface",
        "transformers",
        "blueberries_voi.web",
        "web",
    }
)


def _weekday(day: int) -> int:
    return (_EPOCH + timedelta(days=day)).weekday()


def _resolve_module() -> Any:
    last_err: Exception | None = None
    for name in _MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        "T-077 OrderSchedule module missing; tried "
        f"{_MODULE_CANDIDATES}{detail}",
        pytrace=False,
    )


def _resolve_attr(name: str) -> Any:
    mod = _resolve_module()
    found = getattr(mod, name, None)
    if found is not None:
        return found
    for pkg_name in _PACKAGE_EXPORT_CANDIDATES:
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            continue
        found = getattr(pkg, name, None)
        if found is not None:
            return found
    pytest.fail(
        f"{name} must be exported from {_MODULE_CANDIDATES} "
        f"(or package __all__ on {_PACKAGE_EXPORT_CANDIDATES}) "
        "per .team/specs/T-077.md / ADR 0111",
        pytrace=False,
    )


def _default_schedule() -> Any:
    schedule = _resolve_attr("DEFAULT_ORDER_SCHEDULE")
    cls = _resolve_attr("OrderSchedule")
    assert isinstance(schedule, cls), (
        "DEFAULT_ORDER_SCHEDULE must be an OrderSchedule instance"
    )
    return schedule


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
            roots.add(node.module)
    return roots


# ---------------------------------------------------------------------------
# AC: frozen OrderSchedule with MWF / LT=1 / SunTueThu defaults
# ---------------------------------------------------------------------------


def test_order_schedule_module_is_importable() -> None:
    mod = _resolve_module()
    assert mod.__name__ in _MODULE_CANDIDATES


def test_order_schedule_type_is_frozen_dataclass() -> None:
    cls = _resolve_attr("OrderSchedule")
    assert dataclasses.is_dataclass(cls), "OrderSchedule must be a dataclass"
    assert dataclasses.fields(cls), "OrderSchedule must declare fields"
    # frozen=True → instances reject attribute assignment
    schedule = cls()
    with pytest.raises(dataclasses.FrozenInstanceError):
        schedule.lead_time_days = 99  # type: ignore[misc]


def test_default_order_schedule_mwf_lt1_order_days() -> None:
    schedule = _default_schedule()
    assert frozenset(schedule.delivery_weekdays) == _DEFAULT_DELIVERY
    assert int(schedule.lead_time_days) == _DEFAULT_LEAD_TIME
    assert frozenset(schedule.order_weekdays) == _DEFAULT_ORDER


def test_order_schedule_constructor_defaults_match_base_case() -> None:
    cls = _resolve_attr("OrderSchedule")
    schedule = cls()
    assert frozenset(schedule.delivery_weekdays) == _DEFAULT_DELIVERY
    assert int(schedule.lead_time_days) == _DEFAULT_LEAD_TIME
    assert frozenset(schedule.order_weekdays) == _DEFAULT_ORDER


# ---------------------------------------------------------------------------
# AC: can_order True exactly on order weekdays for days 0..20
# ---------------------------------------------------------------------------


def test_can_order_matches_epoch_weekdays_over_multi_week_range() -> None:
    schedule = _default_schedule()
    for day in range(0, 21):
        expected = _weekday(day) in _DEFAULT_ORDER
        assert schedule.can_order(day) is expected, (
            f"day={day} weekday={_weekday(day)}: "
            f"can_order={schedule.can_order(day)!r}, expected={expected!r}"
        )


# ---------------------------------------------------------------------------
# AC: can_order False on Mon/Wed/Fri (delivery) and Saturday
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "label"),
    [
        (0, "Monday"),
        (2, "Wednesday"),
        (4, "Friday"),
        (5, "Saturday"),
        (7, "Monday+7"),
        (9, "Wednesday+7"),
        (11, "Friday+7"),
        (12, "Saturday+7"),
    ],
)
def test_can_order_false_on_delivery_days_and_saturday(day: int, label: str) -> None:
    schedule = _default_schedule()
    assert schedule.can_order(day) is False, (
        f"can_order must be False on {label} (day={day}, weekday={_weekday(day)})"
    )


# ---------------------------------------------------------------------------
# AC: protection_days 3 / 3 / 4 on Sun / Tue / Thu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "expected", "label"),
    [
        (6, 3, "Sunday"),  # first Sunday in epoch week
        (1, 3, "Tuesday"),
        (3, 4, "Thursday"),
        (13, 3, "Sunday+7"),
        (8, 3, "Tuesday+7"),
        (10, 4, "Thursday+7"),
    ],
)
def test_protection_days_sun_tue_thu(day: int, expected: int, label: str) -> None:
    schedule = _default_schedule()
    assert schedule.can_order(day) is True, f"{label} day={day} must be an order day"
    assert schedule.protection_days(day) == expected, (
        f"protection_days({day}) on {label} must be {expected} (ADR 0111 3/3/4)"
    )


# ---------------------------------------------------------------------------
# AC: next_order_day strictly after day
# ---------------------------------------------------------------------------


def test_next_order_day_strictly_after_monday_lands_on_tuesday() -> None:
    schedule = _default_schedule()
    # day 0 = Monday (non-order) → next order Tuesday = day 1
    assert schedule.can_order(0) is False
    nxt = schedule.next_order_day(0)
    assert nxt == 1
    assert nxt > 0
    assert schedule.can_order(nxt) is True


def test_next_order_day_from_order_day_skips_today() -> None:
    schedule = _default_schedule()
    # Tuesday day 1 is an order day; successor must be Thursday day 3
    assert schedule.can_order(1) is True
    nxt = schedule.next_order_day(1)
    assert nxt == 3
    assert nxt > 1
    assert schedule.can_order(nxt) is True


def test_next_order_day_is_smallest_strict_successor() -> None:
    schedule = _default_schedule()
    for day in range(0, 21):
        nxt = schedule.next_order_day(day)
        assert nxt > day, f"next_order_day({day}) must be strictly after day"
        assert schedule.can_order(nxt) is True
        for mid in range(day + 1, nxt):
            assert schedule.can_order(mid) is False, (
                f"next_order_day({day})={nxt} but can_order({mid}) is True"
            )


# ---------------------------------------------------------------------------
# AC: epoch weekday alignment — day 0 = Monday 2024-01-01
# ---------------------------------------------------------------------------


def test_epoch_day_zero_is_monday_2024_01_01() -> None:
    assert _EPOCH == date(2024, 1, 1)
    assert _EPOCH.weekday() == 0  # Monday
    assert _weekday(0) == 0
    assert _weekday(1) == 1  # Tuesday
    assert _weekday(6) == 6  # Sunday


def test_order_schedule_uses_epoch_monday_alignment() -> None:
    """Fail loudly if implementation drifts off the ASN epoch clock."""
    schedule = _default_schedule()
    # Absolute anchors from the locked epoch (not relative-only arithmetic).
    assert schedule.can_order(0) is False  # Mon 2024-01-01
    assert schedule.can_order(1) is True  # Tue 2024-01-02
    assert schedule.can_order(6) is True  # Sun 2024-01-07
    # If someone silently shifted epoch by one day, Mon would look like Sun.
    assert date(2024, 1, 1).weekday() == 0
    assert schedule.can_order(0) is not True


# ---------------------------------------------------------------------------
# AC: public export path without HF / datasets / web
# ---------------------------------------------------------------------------


def test_order_schedule_exported_on_package_all_or_documented_module() -> None:
    mod = _resolve_module()
    assert hasattr(mod, "OrderSchedule")
    assert hasattr(mod, "DEFAULT_ORDER_SCHEDULE")
    exported = False
    if hasattr(mod, "__all__"):
        all_names = set(mod.__all__)
        exported = "OrderSchedule" in all_names and "DEFAULT_ORDER_SCHEDULE" in all_names
    for pkg_name in _PACKAGE_EXPORT_CANDIDATES:
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            continue
        pkg_all = getattr(pkg, "__all__", None)
        if pkg_all is not None and "OrderSchedule" in pkg_all:
            exported = True
            break
        if getattr(pkg, "OrderSchedule", None) is not None:
            exported = True
            break
    assert exported, (
        "OrderSchedule must be on module __all__ or a Track A package export "
        f"({_PACKAGE_EXPORT_CANDIDATES})"
    )


def test_importing_order_schedule_does_not_load_hf_or_web() -> None:
    # Drop any prior loads so the check sees a fresh import graph.
    doomed = [
        name
        for name in list(sys.modules)
        if name.startswith("blueberries_voi.sim.order_schedule")
        or name.startswith("blueberries_voi.controller.order_schedule")
        or name in _FORBIDDEN_IMPORT_ROOTS
        or name.startswith("datasets")
        or name.startswith("huggingface")
    ]
    for name in doomed:
        sys.modules.pop(name, None)

    mod = _resolve_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file(), f"missing source for {mod.__name__}"
    forbidden = _imported_roots(path) & _FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, (
        f"{path.name} must not import HF/datasets/web: {sorted(forbidden)}"
    )
    for root in ("datasets", "huggingface_hub", "huggingface", "transformers"):
        assert root not in sys.modules, (
            f"importing OrderSchedule must not load {root!r} into sys.modules"
        )


def test_order_schedule_module_lives_under_track_a() -> None:
    mod = _resolve_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file()
    assert path.name == "order_schedule.py"
    assert "sim" in path.parts or "controller" in path.parts
    assert path.is_relative_to(_SRC)
