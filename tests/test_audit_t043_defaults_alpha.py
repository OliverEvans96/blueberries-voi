"""T-043: DEFAULT_PROFIT_COSTS, Abdella shipment defaults, VOI alpha-table gate.

See `.team/specs/T-043-audit-remediation.md` and ADR 0104. Abdella defaults may
use ``data/abdella/`` or monkeypatch; cool fixtures must be explicitly named
``smoke_cool_shipments``.
"""

from __future__ import annotations

import pytest

pytest.skip(
    "T-121 F3: ADR 0127 Wave F supersession — VOI CRN Python episode audit removed",
    allow_module_level=True,
)

import importlib
import inspect
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.model.abdella import ShipmentTrace

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROFIT_MOD = "blueberries_voi.sim.profit"
_PRODUCTION_COST_MODULES: tuple[str, ...] = (
    "blueberries_voi.voi.crn",
    "blueberries_voi.sim.m2_ladder",
    "blueberries_voi.sim.m2_multi_scenario",
    "blueberries_voi.sim.alpha_tune",
)

_EXPECTED_MARGIN = 2.0
_EXPECTED_WASTE = 1.5
_EXPECTED_STOCKOUT = 3.0


def _resolve_attr(module: str, attr: str) -> Any:
    try:
        mod = importlib.import_module(module)
    except ImportError as exc:
        pytest.fail(f"{module} must import for T-043 ({attr}): {exc}", pytrace=False)
    found = getattr(mod, attr, None)
    assert found is not None, f"{attr} must be exported from {module} (T-043)"
    return found


def _find_smoke_cool() -> Any:
    """Locate public smoke_cool_shipments (or documented alias)."""
    candidates = (
        ("blueberries_voi.sim.shipments", "smoke_cool_shipments"),
        ("blueberries_voi.sim", "smoke_cool_shipments"),
        ("blueberries_voi.model.abdella", "smoke_cool_shipments"),
        ("blueberries_voi.voi.crn", "smoke_cool_shipments"),
        ("blueberries_voi.sim.alpha_tune", "smoke_cool_shipments"),
        ("blueberries_voi.sim.m2_ladder", "smoke_cool_shipments"),
    )
    for mod_name, attr in candidates:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        fn = getattr(mod, attr, None)
        if callable(fn):
            return fn
    # Alias names allowed by spec
    for mod_name in (
        "blueberries_voi.sim",
        "blueberries_voi.sim.shipments",
        "blueberries_voi.voi.crn",
    ):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for alias in ("smoke_cool_shipments", "cool_smoke_shipments"):
            fn = getattr(mod, alias, None)
            if callable(fn):
                return fn
    pytest.fail(
        "public smoke_cool_shipments (or documented alias) must be importable (T-043)",
        pytrace=False,
    )


def _find_default_shipments() -> Any | None:
    for mod_name in (
        "blueberries_voi.sim.shipments",
        "blueberries_voi.sim",
        "blueberries_voi.model.abdella",
        "blueberries_voi.voi.crn",
    ):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        fn = getattr(mod, "default_shipments", None)
        if callable(fn):
            return fn
    return None


def _write_complete_alpha_table(path: Path, *, sw_alpha: float = 0.75) -> Path:
    table = {
        "constant": 0.8,
        "rung0": 0.8,
        "sw": float(sw_alpha),
        "rollout": 0.8,
        "dp": 0.8,
    }
    save = importlib.import_module(
        "blueberries_voi.sim.alpha_tune"
    ).save_tuned_alpha_table
    save(path, table)
    return path


def _minimal_cool_like(ships: list[ShipmentTrace]) -> bool:
    """Heuristic: synthetic 1°C cool fixture (not Abdella parquet traces)."""
    if not ships:
        return False
    temps = np.asarray(ships[0].temps_c, dtype=float)
    return bool(temps.size) and bool(np.allclose(temps, 1.0))


# ---------------------------------------------------------------------------
# AC: DEFAULT_PROFIT_COSTS on sim/profit.py + uncalibrated docs
# ---------------------------------------------------------------------------


def test_default_profit_costs_exported_with_scaffold_values() -> None:
    costs = _resolve_attr(_PROFIT_MOD, "DEFAULT_PROFIT_COSTS")
    assert costs.unit_margin == _EXPECTED_MARGIN
    assert costs.waste_cost == _EXPECTED_WASTE
    assert costs.stockout_penalty == _EXPECTED_STOCKOUT


def test_default_profit_costs_documented_as_uncalibrated() -> None:
    mod = importlib.import_module(_PROFIT_MOD)
    _resolve_attr(_PROFIT_MOD, "DEFAULT_PROFIT_COSTS")
    # Constant docstring, or module docstring adjacent to the constant.
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    blob = f"{mod.__doc__ or ''}\n{source}".lower()
    assert "uncalibrated" in blob, (
        "DEFAULT_PROFIT_COSTS must be documented as uncalibrated scaffold costs "
        "(module docstring or adjacent comment/doc on the constant)"
    )
    assert "DEFAULT_PROFIT_COSTS" in source


# ---------------------------------------------------------------------------
# AC: production modules resolve costs is None → DEFAULT_PROFIT_COSTS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mod_name", _PRODUCTION_COST_MODULES)
def test_production_modules_use_shared_default_profit_costs(mod_name: str) -> None:
    mod = importlib.import_module(mod_name)
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "DEFAULT_PROFIT_COSTS" in source, (
        f"{mod_name} must resolve costs is None via DEFAULT_PROFIT_COSTS (T-043)"
    )
    # No private duplicate of the three-number scaffold.
    assert "_DEFAULT_COSTS = ProfitCosts(" not in source, (
        f"{mod_name} must not keep a private _DEFAULT_COSTS ProfitCosts literal "
        "(use shared DEFAULT_PROFIT_COSTS)"
    )


def test_voi_crn_none_costs_uses_default_profit_costs_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Observable: episode_profit receives DEFAULT_PROFIT_COSTS when costs is None."""
    default_costs = _resolve_attr(_PROFIT_MOD, "DEFAULT_PROFIT_COSTS")
    from blueberries_voi.sim.profit import episode_profit as real_profit
    from blueberries_voi.voi import crn as crn_mod

    assert crn_mod.__file__ is not None
    source = Path(crn_mod.__file__).read_text(encoding="utf-8")
    assert "DEFAULT_PROFIT_COSTS" in source, (
        "voi.crn must wire DEFAULT_PROFIT_COSTS (T-043)"
    )

    captured: list[Any] = []

    def _spy(ep: Any, costs: Any) -> float:
        captured.append(costs)
        return real_profit(ep, costs)

    monkeypatch.setattr(crn_mod, "episode_profit", _spy)

    ships = [
        ShipmentTrace(
            shipment_id="T043",
            times_d=np.asarray([0.0, 1.0], dtype=float),
            temps_c=np.asarray([1.0, 1.0], dtype=float),
            duration_d=1.0,
        )
    ]
    kwargs: dict[str, Any] = {
        "beta": 1.0,
        "root_seed": 0,
        "scenarios": ["B-state"],
        "n_burn": 1,
        "n_score": 1,
        "filter_n": 8,
        "H": 1,
        "n_rollout_paths": 1,
        "shipments": ships,
        "costs": None,
    }
    sig = inspect.signature(crn_mod.run_voi_crn_cell)
    if "alpha_table_path" in sig.parameters:
        table = _write_complete_alpha_table(tmp_path / "alphas.json", sw_alpha=0.75)
        kwargs["alpha_table_path"] = table

    crn_mod.run_voi_crn_cell(**kwargs)
    assert captured, "episode_profit not called"
    used = captured[0]
    assert used == default_costs or used is default_costs


# ---------------------------------------------------------------------------
# AC: shipments is None → Abdella (not cool fixture)
# ---------------------------------------------------------------------------


def test_smoke_cool_shipments_returns_1c_cool_without_abdella(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _find_smoke_cool()

    def _boom(*_a: Any, **_k: Any) -> list[ShipmentTrace]:
        raise AssertionError("smoke_cool_shipments must not load Abdella parquet")

    import blueberries_voi.model.abdella as abdella

    monkeypatch.setattr(abdella, "load_abdella_shipments", _boom)
    ships = smoke()
    assert isinstance(ships, list) and ships
    assert all(isinstance(s, ShipmentTrace) for s in ships)
    assert _minimal_cool_like(ships), (
        "smoke helper must return synthetic 1°C cool traces"
    )


def test_production_voi_crn_default_shipments_load_abdella(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from blueberries_voi.voi import crn as crn_mod

    calls: list[str] = []
    sentinel = [
        ShipmentTrace(
            shipment_id="ABDELLA-SENTINEL",
            times_d=np.asarray([0.0, 1.0], dtype=float),
            temps_c=np.asarray([3.0, 3.0], dtype=float),
            duration_d=1.0,
        )
    ]

    def _fake_load(root: Any = None) -> list[ShipmentTrace]:
        calls.append("load_abdella_shipments")
        return list(sentinel)

    import blueberries_voi.model.abdella as abdella

    monkeypatch.setattr(abdella, "load_abdella_shipments", _fake_load)
    if hasattr(crn_mod, "load_abdella_shipments"):
        monkeypatch.setattr(crn_mod, "load_abdella_shipments", _fake_load)
    default_fn = _find_default_shipments()
    if default_fn is not None:
        # If default_shipments lives elsewhere, patch load underneath it too.
        monkeypatch.setattr(
            importlib.import_module(default_fn.__module__),
            "load_abdella_shipments",
            _fake_load,
            raising=False,
        )

    # Patch private cool fixture if still present — must not be the default path.
    if hasattr(crn_mod, "_fixture_shipments"):

        def _cool_boom() -> list[ShipmentTrace]:
            raise AssertionError(
                "production default must not call cool _fixture_shipments (T-043)"
            )

        monkeypatch.setattr(crn_mod, "_fixture_shipments", _cool_boom)

    kwargs: dict[str, Any] = {
        "beta": 1.0,
        "root_seed": 1,
        "scenarios": ["B-state"],
        "n_burn": 1,
        "n_score": 1,
        "filter_n": 8,
        "H": 1,
        "n_rollout_paths": 1,
        "shipments": None,
    }
    sig = inspect.signature(crn_mod.run_voi_crn_cell)
    if "alpha_table_path" in sig.parameters:
        kwargs["alpha_table_path"] = _write_complete_alpha_table(
            tmp_path / "alphas.json"
        )

    # Also patch default_shipments on crn if it imports a local binding.
    for name in ("default_shipments", "load_abdella_shipments"):
        if hasattr(crn_mod, name):
            monkeypatch.setattr(
                crn_mod,
                name,
                _fake_load
                if name == "load_abdella_shipments"
                else (lambda **_k: _fake_load()),
            )

    crn_mod.run_voi_crn_cell(**kwargs)
    assert calls, (
        "run_voi_crn_cell(shipments=None) must load Abdella via "
        "load_abdella_shipments / default_shipments (T-043)"
    )


@pytest.mark.parametrize(
    ("mod_name", "fn_name"),
    [
        ("blueberries_voi.sim.m2_ladder", "run_m2_ladder"),
        ("blueberries_voi.sim.m2_multi_scenario", "run_m2_multi_scenario"),
        ("blueberries_voi.sim.alpha_tune", "evaluate_alpha_episode_profit"),
    ],
)
def test_m2_and_alpha_default_shipments_not_cool_fixture(
    mod_name: str,
    fn_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name, None)
    assert callable(fn), f"{mod_name}.{fn_name} required for T-043"

    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    # Default path: Abdella load or default_shipments, not only cool fixture.
    uses_abdella = "load_abdella_shipments" in source or "default_shipments" in source
    still_defaults_cool = (
        "shipments) if shipments is not None else _fixture_shipments()" in source
        or "else _fixture_shipments()" in source
    )
    assert uses_abdella and not still_defaults_cool, (
        f"{mod_name} must default shipments=None to Abdella / default_shipments, "
        f"not _fixture_shipments cool path (T-043)"
    )


def test_default_shipments_helper_calls_abdella(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_fn = _find_default_shipments()
    assert default_fn is not None, (
        "public default_shipments() that calls load_abdella_shipments is required "
        "(T-043 interface)"
    )
    calls: list[Any] = []

    def _fake(root: Any = None) -> list[ShipmentTrace]:
        calls.append(root)
        return [
            ShipmentTrace(
                shipment_id="X",
                times_d=np.asarray([0.0], dtype=float),
                temps_c=np.asarray([2.0], dtype=float),
                duration_d=1.0,
            )
        ]

    import blueberries_voi.model.abdella as abdella

    monkeypatch.setattr(abdella, "load_abdella_shipments", _fake)
    monkeypatch.setattr(
        importlib.import_module(default_fn.__module__),
        "load_abdella_shipments",
        _fake,
        raising=False,
    )
    out = default_fn()
    assert calls, "default_shipments must call load_abdella_shipments"
    assert out and out[0].shipment_id == "X"


# ---------------------------------------------------------------------------
# AC: production VOI alpha-table gate; smoke may keep alpha=0.9
# ---------------------------------------------------------------------------


def test_production_voi_crn_requires_tuned_alpha_table(tmp_path: Path) -> None:
    from blueberries_voi.voi.crn import run_voi_crn_cell

    ships = [
        ShipmentTrace(
            shipment_id="T043",
            times_d=np.asarray([0.0, 1.0], dtype=float),
            temps_c=np.asarray([1.0, 1.0], dtype=float),
            duration_d=1.0,
        )
    ]
    sig = inspect.signature(run_voi_crn_cell)
    assert "alpha_table_path" in sig.parameters, (
        "run_voi_crn_cell must accept alpha_table_path (or equivalent) for CTL-03 gate"
    )
    missing = tmp_path / "missing_alphas.json"
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        run_voi_crn_cell(
            beta=1.0,
            root_seed=0,
            scenarios=["B-state"],
            n_burn=1,
            n_score=1,
            filter_n=8,
            H=1,
            n_rollout_paths=1,
            shipments=ships,
            alpha_table_path=missing,
        )


def test_production_voi_crn_uses_table_alpha_not_hardcoded_0_9(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from blueberries_voi.controller import damped_sw
    from blueberries_voi.voi import crn as crn_mod

    table_alpha = 0.73
    table = _write_complete_alpha_table(tmp_path / "alphas.json", sw_alpha=table_alpha)
    seen: list[float] = []
    Real = damped_sw.DampedSurvivalWeightedPolicy

    class _SpyPolicy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            alpha = kwargs.get("alpha", args[0] if args else None)
            if alpha is not None:
                seen.append(float(alpha))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(damped_sw, "DampedSurvivalWeightedPolicy", _SpyPolicy)
    if hasattr(crn_mod, "DampedSurvivalWeightedPolicy"):
        monkeypatch.setattr(crn_mod, "DampedSurvivalWeightedPolicy", _SpyPolicy)

    ships = [
        ShipmentTrace(
            shipment_id="T043",
            times_d=np.asarray([0.0, 1.0], dtype=float),
            temps_c=np.asarray([1.0, 1.0], dtype=float),
            duration_d=1.0,
        )
    ]
    sig = inspect.signature(crn_mod.run_voi_crn_cell)
    assert "alpha_table_path" in sig.parameters
    crn_mod.run_voi_crn_cell(
        beta=1.0,
        root_seed=2,
        scenarios=["B-state"],
        n_burn=1,
        n_score=1,
        filter_n=8,
        H=1,
        n_rollout_paths=1,
        shipments=ships,
        alpha_table_path=table,
    )
    assert seen, "expected DampedSurvivalWeightedPolicy construction"
    assert table_alpha in seen, (
        f"production VOI must use tuned table alpha={table_alpha}, got {seen} "
        "(must not silently hardcode 0.9)"
    )


def test_smoke_voi_allows_fixed_alpha_without_table() -> None:
    """Smoke path must not require an alpha-table artifact (fixed alpha=0.9 allowed)."""
    from blueberries_voi.voi import sweep as sweep_mod

    smoke_sig = inspect.signature(sweep_mod.run_voi_smoke)
    assert "alpha_table_path" not in smoke_sig.parameters or (
        smoke_sig.parameters["alpha_table_path"].default is None
    )
    # Source contract: smoke=True path does not call require_tuned_alpha_table.
    assert sweep_mod.__file__ is not None
    source = Path(sweep_mod.__file__).read_text(encoding="utf-8")
    # Production (smoke=False) must gate; smoke helper itself stays ungated.
    assert "def run_voi_smoke" in source
    # Calling smoke without a table must not raise for missing alpha artifact.
    # Keep budgets tiny via run_voi_sweep(smoke=True) rather than full report I/O.
    try:
        result = sweep_mod.run_voi_sweep(
            smoke=True,
            root_seed=0,
            scenarios=["B-state"],
            betas=[1.0],
            n_replications=1,
            n_burn=1,
            n_score=1,
            filter_n=8,
            H=1,
            n_rollout_paths=1,
            n_bootstrap=2,
        )
    except TypeError:
        # If production gate added alpha_table_path only on non-smoke, call as today.
        result = sweep_mod.run_voi_sweep(
            smoke=True,
            root_seed=0,
            scenarios=["B-state"],
            betas=[1.0],
        )
    assert result is not None
    assert bool(getattr(result, "smoke", True)) is True
