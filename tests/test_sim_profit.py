"""T-025: day / episode profit helper (SIM-01=B) — expected RED until sim/profit.py."""

from __future__ import annotations

import ast
import dataclasses
import re
import tomllib
from pathlib import Path

import pytest

from blueberries_voi.sim import DayLog, EpisodeLog, LotState

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_DEPS_LOCKED = frozenset({"matplotlib", "numpy", "pyarrow", "scipy"})


def _day(
    *,
    day: int = 0,
    sales: int = 0,
    waste: int = 0,
    demand: int = 0,
    on_hand: int = 0,
) -> DayLog:
    lots = [LotState(n=on_hand, tau=1.0, lot_id=1)] if on_hand > 0 else []
    return DayLog(
        day=day,
        lots=lots,
        sales_total=sales,
        waste_total=waste,
        arrivals=0,
        order_qty=0,
        demand=demand,
        L=len(lots),
    )


def _costs(
    *,
    unit_margin: float = 2.0,
    waste_cost: float = 1.5,
    stockout_penalty: float = 3.0,
) -> object:
    from blueberries_voi.sim.profit import ProfitCosts

    return ProfitCosts(
        unit_margin=unit_margin,
        waste_cost=waste_cost,
        stockout_penalty=stockout_penalty,
    )


def _expected(
    sales: int,
    waste: int,
    demand: int,
    *,
    unit_margin: float = 2.0,
    waste_cost: float = 1.5,
    stockout_penalty: float = 3.0,
) -> float:
    lost = max(0, demand - sales)
    return unit_margin * sales - waste_cost * waste - stockout_penalty * lost


# --- AC: day_profit formula (SIM-01=B) ---


def test_day_profit_matches_sim01_b_formula() -> None:
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=10, waste=2, demand=12)
    costs = _costs()
    assert day_profit(day, costs) == _expected(10, 2, 12)


def test_day_profit_zero_stockout_when_sales_meet_demand() -> None:
    """AC: zero stockout case — lost sales term is zero."""
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=8, waste=1, demand=8)
    costs = _costs()
    got = day_profit(day, costs)
    assert got == _expected(8, 1, 8)
    assert got == 2.0 * 8 - 1.5 * 1 - 3.0 * 0


def test_day_profit_pure_waste_no_sales_no_demand() -> None:
    """AC: pure waste — only waste cost subtracted."""
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=0, waste=5, demand=0)
    costs = _costs()
    assert day_profit(day, costs) == _expected(0, 5, 0)
    assert day_profit(day, costs) == -1.5 * 5


def test_day_profit_pure_lost_sales_no_waste() -> None:
    """AC: pure lost-sales — only stockout penalty subtracted."""
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=0, waste=0, demand=7)
    costs = _costs()
    assert day_profit(day, costs) == _expected(0, 0, 7)
    assert day_profit(day, costs) == -3.0 * 7


def test_day_profit_lost_sales_clamped_when_sales_exceed_demand() -> None:
    """Boundary: max(0, demand - sales) → 0 when sales > demand."""
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=10, waste=0, demand=6)
    costs = _costs()
    assert day_profit(day, costs) == _expected(10, 0, 6)
    assert day_profit(day, costs) == 2.0 * 10


def test_day_profit_all_zeros_is_zero() -> None:
    from blueberries_voi.sim.profit import day_profit

    day = _day(sales=0, waste=0, demand=0)
    costs = _costs()
    assert day_profit(day, costs) == 0.0


# --- AC: holding cost not subtracted (SIM-01=B) ---


def test_day_profit_does_not_subtract_holding_cost() -> None:
    """AC: inventory / on-hand must not change day profit under SIM-01=B."""
    from blueberries_voi.sim.profit import day_profit

    lean = _day(sales=4, waste=1, demand=5, on_hand=0)
    fat = _day(sales=4, waste=1, demand=5, on_hand=40)
    costs = _costs()
    expected = _expected(4, 1, 5)
    assert day_profit(lean, costs) == expected
    assert day_profit(fat, costs) == expected
    assert day_profit(fat, costs) == day_profit(lean, costs)


# --- AC: episode_profit over scored days only (SIM-03) ---


def test_episode_profit_sums_scored_days_only() -> None:
    from blueberries_voi.sim.profit import day_profit, episode_profit

    burn = [
        _day(day=0, sales=100, waste=0, demand=100),
        _day(day=1, sales=100, waste=0, demand=100),
    ]
    scored = [
        _day(day=2, sales=3, waste=1, demand=4),
        _day(day=3, sales=5, waste=0, demand=5),
    ]
    episode = EpisodeLog(days=burn + scored, n_burn=2, n_score=2)
    costs = _costs()

    got = episode_profit(episode, costs)
    expected = sum(day_profit(d, costs) for d in episode.scored)
    assert got == expected
    assert got == _expected(3, 1, 4) + _expected(5, 0, 5)
    # Burn-in profits must not be included.
    burn_total = sum(day_profit(d, costs) for d in burn)
    assert got != burn_total + expected


def test_episode_profit_empty_scored_window_is_zero() -> None:
    """Boundary: all days in burn-in → episode profit 0."""
    from blueberries_voi.sim.profit import episode_profit

    episode = EpisodeLog(
        days=[_day(day=0, sales=50, waste=0, demand=50)],
        n_burn=1,
        n_score=0,
    )
    costs = _costs()
    assert episode_profit(episode, costs) == 0.0


def test_episode_profit_n_burn_zero_sums_all_days() -> None:
    from blueberries_voi.sim.profit import day_profit, episode_profit

    days = [
        _day(day=0, sales=2, waste=0, demand=2),
        _day(day=1, sales=0, waste=3, demand=0),
    ]
    episode = EpisodeLog(days=days, n_burn=0, n_score=2)
    costs = _costs()
    assert episode_profit(episode, costs) == sum(day_profit(d, costs) for d in days)


# --- AC: I/O-free / no matplotlib ---


def test_profit_module_does_not_import_matplotlib() -> None:
    import blueberries_voi.sim.profit as profit

    assert profit.__file__ is not None
    tree = ast.parse(Path(profit.__file__).read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    assert "matplotlib" not in roots
    assert "pyplot" not in roots


def test_profit_module_has_no_filesystem_io_calls() -> None:
    import blueberries_voi.sim.profit as profit

    assert profit.__file__ is not None
    tree = ast.parse(Path(profit.__file__).read_text(encoding="utf-8"))
    banned_names = {
        "open",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "remove",
        "rename",
        "replace",
    }
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in banned_names:
                found.add(func.id)
            elif isinstance(func, ast.Attribute) and func.attr in banned_names:
                found.add(func.attr)
    assert not found, f"profit helper must not perform filesystem I/O; found {found}"


# --- AC: ProfitCosts contract + no new runtime deps ---


def test_profit_costs_is_frozen_dataclass() -> None:
    from blueberries_voi.sim.profit import ProfitCosts

    costs = ProfitCosts(unit_margin=1.0, waste_cost=2.0, stockout_penalty=3.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        costs.unit_margin = 9.0  # type: ignore[misc]


def test_no_new_runtime_dependencies_for_t025() -> None:
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _RUNTIME_DEPS_LOCKED, (
        f"runtime dependencies changed for T-025: {sorted(names)} "
        f"(locked {sorted(_RUNTIME_DEPS_LOCKED)})"
    )
