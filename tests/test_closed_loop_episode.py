"""T-024: closed-loop episode driver + Policy protocol (RED).

Policy-driven episodes must take injectable ``shipments=`` and must not default to
Abdella parquet / ``load_abdella_shipments``. Open-loop ``run_episode`` may keep its
legacy FS default separately.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from blueberries_voi import model as model_pkg
from blueberries_voi import sim as sim_pkg
from blueberries_voi._type_compat import is_same_package_type
from blueberries_voi.sim.bakeoff_ordering import case_round
from blueberries_voi.model import ModelParams, day_step
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.rng import (
    STREAM_ALLOC,
    STREAM_ARRIVAL_SENSOR,
    STREAM_ARRIVAL_SHIP,
    STREAM_DEMAND,
    STREAM_FILTER_RESAMPLE,
    STREAM_SPOIL,
    spawn_rng,
)
from blueberries_voi.sim import EpisodeLog
from blueberries_voi.sim.order_schedule import DEFAULT_ORDER_SCHEDULE

# T-079: closed-loop orders only on schedule days (default Sun/Tue/Thu).
_EPISODE_EPOCH = date(2024, 1, 1)


def _is_order_day(day: int) -> bool:
    return bool(DEFAULT_ORDER_SCHEDULE.can_order(day))


def _weekday(day: int) -> int:
    return (_EPISODE_EPOCH + timedelta(days=day)).weekday()


# ---------------------------------------------------------------------------
# Fixtures / helpers (no Abdella FS)
# ---------------------------------------------------------------------------


def _fixture_shipments() -> list[ShipmentTrace]:
    """Minimal in-memory traces — no parquet, no repo ``data/`` paths."""
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="FIX-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="FIX-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _case_nearest_units(order_qty: int, case_size: int) -> int:
    """Match closed-loop / controller nearest case rounding (T-042)."""
    return int(case_round(float(order_qty), case_size))


def _resolve_policy_type() -> type[Any]:
    """Public ``Policy`` protocol/ABC from ``sim.episode`` or ``sim``."""
    for mod_name in ("blueberries_voi.sim.episode", "blueberries_voi.sim"):
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            continue
        policy = getattr(mod, "Policy", None)
        if policy is not None:
            return cast("type[Any]", policy)
    raise AssertionError(
        "missing public Policy protocol/ABC under blueberries_voi.sim "
        "(or blueberries_voi.sim.episode)"
    )


def _resolve_closed_loop_runner() -> Callable[..., EpisodeLog]:
    """Resolve ``run_closed_loop_episode`` or ``run_episode(policy=...)``."""
    candidates: list[Callable[..., EpisodeLog]] = []
    for mod_name in ("blueberries_voi.sim.episode", "blueberries_voi.sim"):
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            continue
        fn = getattr(mod, "run_closed_loop_episode", None)
        if callable(fn):
            candidates.append(fn)
    if candidates:
        return candidates[0]

    open_loop = sim_pkg.run_episode
    params = inspect.signature(open_loop).parameters
    if "policy" in params:
        return open_loop

    raise AssertionError(
        "missing closed-loop entry: expected run_closed_loop_episode under "
        "blueberries_voi.sim(.episode), or run_episode accepting policy="
    )


def _closed_loop_accepts_shipments(runner: Callable[..., EpisodeLog]) -> bool:
    return "shipments" in inspect.signature(runner).parameters


def _run_closed_loop(
    policy: Any,
    *,
    shipments: Sequence[ShipmentTrace],
    params: ModelParams | None = None,
    root_seed: int = 0,
    run_id: str | int = "t024",
    n_burn: int = 2,
    n_score: int = 5,
    lead_time: int = 1,
    **extra: Any,
) -> EpisodeLog:
    runner = _resolve_closed_loop_runner()
    assert _closed_loop_accepts_shipments(runner), (
        "Policy-driven episode must accept injectable shipments= "
        "(no Abdella FS default on this path)"
    )
    kwargs: dict[str, Any] = {
        "shipments": shipments,
        "params": params or ModelParams(),
        "root_seed": root_seed,
        "run_id": run_id,
        "n_burn": n_burn,
        "n_score": n_score,
        "lead_time": lead_time,
        **extra,
    }
    # Dedicated closed-loop name takes policy positionally/keyword; extended
    # open-loop takes policy= keyword.
    if getattr(runner, "__name__", "") == "run_episode":
        return runner(policy=policy, **kwargs)
    try:
        return runner(policy, **kwargs)
    except TypeError:
        return runner(policy=policy, **kwargs)


class _ConstantOrderPolicy:
    """Local stub for Policy.order surface (T-026 lives elsewhere)."""

    def __init__(self, q: int) -> None:
        self.q = int(q)
        self.calls: list[tuple[int, object | None, Mapping[int, int]]] = []

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
        **_kwargs: Any,
    ) -> int:
        pending = pending_orders if pending_orders is not None else {}
        self.calls.append((int(day), belief, dict(pending)))
        return max(0, self.q)


class _RecordingBeliefPolicy:
    """Records belief / pending kwargs; returns a fixed non-negative order."""

    def __init__(self, q: int = 8) -> None:
        self.q = int(q)
        self.days: list[int] = []
        self.beliefs: list[object | None] = []
        self.pendings: list[Mapping[int, int]] = []

    def order(
        self,
        day: int,
        belief: object | None = None,
        *,
        pending_orders: Mapping[int, int] | None = None,
        **_kwargs: Any,
    ) -> int:
        self.days.append(int(day))
        self.beliefs.append(belief)
        self.pendings.append(dict(pending_orders or {}))
        return max(0, self.q)


def _patch_abdella_fs_forbidden(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Any accidental Abdella FS load fails the test."""
    calls: list[str] = []

    def _boom(*_a: Any, **_k: Any) -> list[ShipmentTrace]:
        calls.append("load_abdella_shipments")
        raise AssertionError(
            "Policy-driven closed-loop must not call load_abdella_shipments "
            "(inject shipments=; no parquet/FS default)"
        )

    import blueberries_voi.model.abdella as abdella
    import blueberries_voi.sim as sim_mod

    monkeypatch.setattr(abdella, "load_abdella_shipments", _boom)
    if hasattr(sim_mod, "load_abdella_shipments"):
        monkeypatch.setattr(sim_mod, "load_abdella_shipments", _boom)
    try:
        episode = importlib.import_module("blueberries_voi.sim.episode")
    except ModuleNotFoundError:
        episode = None
    if episode is not None and hasattr(episode, "load_abdella_shipments"):
        monkeypatch.setattr(episode, "load_abdella_shipments", _boom)
    return calls


# ---------------------------------------------------------------------------
# AC: Policy protocol
# ---------------------------------------------------------------------------


def test_policy_protocol_is_public_and_order_returns_non_negative_int() -> None:
    Policy = _resolve_policy_type()
    assert inspect.isclass(Policy)
    proto_attrs = set(getattr(Policy, "__protocol_attrs__", ()) or ())
    abstract = set(getattr(Policy, "__abstractmethods__", ()) or ())
    assert "order" in proto_attrs or "order" in abstract or hasattr(Policy, "order"), (
        "Policy must expose an order(...) method"
    )

    class _Ok:
        def order(
            self,
            day: int,
            belief: object | None = None,
            *,
            pending_orders: Mapping[int, int] | None = None,
            **_kwargs: Any,
        ) -> int:
            _ = (day, belief, pending_orders)
            return 0

    if getattr(Policy, "_is_runtime_protocol", False):
        assert isinstance(_Ok(), Policy)

    qty = _Ok().order(0, None, pending_orders={})
    assert isinstance(qty, int)
    assert qty >= 0


def test_policy_order_receives_day_belief_and_pending_orders() -> None:
    ships = _fixture_shipments()
    policy = _RecordingBeliefPolicy(q=8)
    ep = _run_closed_loop(
        policy,
        shipments=ships,
        n_burn=1,
        n_score=3,
        root_seed=11,
        run_id="t024-policy-args",
    )
    horizon = ep.n_burn + ep.n_score
    assert policy.days == list(range(horizon))
    assert len(policy.beliefs) == horizon
    assert len(policy.pendings) == horizon
    for pending in policy.pendings:
        assert isinstance(pending, Mapping)
        for key, val in pending.items():
            assert isinstance(key, int)
            assert isinstance(val, int)
            assert val >= 0


# ---------------------------------------------------------------------------
# AC: closed-loop uses shared day_step + injectable shipments (no FS)
# ---------------------------------------------------------------------------


def test_closed_loop_shares_model_day_step() -> None:
    """ENG-02 / M2 brief: one physics path — same day_step object as model."""
    _ = _resolve_closed_loop_runner()
    assert sim_pkg.day_step is model_pkg.day_step
    assert sim_pkg.day_step is day_step
    try:
        episode = importlib.import_module("blueberries_voi.sim.episode")
    except ModuleNotFoundError:
        episode = None
    if episode is not None and hasattr(episode, "day_step"):
        assert episode.day_step is model_pkg.day_step


def test_closed_loop_requires_injectable_shipments_no_abdella_fs_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _resolve_closed_loop_runner()
    assert _closed_loop_accepts_shipments(runner), (
        "closed-loop API must expose shipments= (required / injectable; "
        "no Abdella FS default on the Policy path)"
    )
    # Missing shipments must not silently load Abdella from disk.
    _patch_abdella_fs_forbidden(monkeypatch)
    policy = _ConstantOrderPolicy(8)
    with pytest.raises((TypeError, ValueError, AssertionError)):
        if getattr(runner, "__name__", "") == "run_episode":
            runner(
                policy=policy,
                params=ModelParams(),
                root_seed=1,
                run_id="no-ships",
                n_burn=1,
                n_score=1,
            )
        else:
            try:
                runner(
                    policy,
                    params=ModelParams(),
                    root_seed=1,
                    run_id="no-ships",
                    n_burn=1,
                    n_score=1,
                )
            except TypeError:
                runner(
                    policy=policy,
                    params=ModelParams(),
                    root_seed=1,
                    run_id="no-ships",
                    n_burn=1,
                    n_score=1,
                )


def test_closed_loop_with_fixture_shipments_does_not_touch_abdella_fs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    policy = _ConstantOrderPolicy(16)
    ep = _run_closed_loop(
        policy,
        shipments=ships,
        n_burn=2,
        n_score=4,
        root_seed=3,
        run_id="t024-no-fs",
    )
    assert is_same_package_type(ep, EpisodeLog)
    assert len(ep.days) == ep.n_burn + ep.n_score
    assert calls == []


def test_closed_loop_empty_shipments_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    policy = _ConstantOrderPolicy(8)
    with pytest.raises(ValueError):
        _run_closed_loop(
            policy,
            shipments=[],
            n_burn=1,
            n_score=1,
            root_seed=0,
            run_id="t024-empty-ships",
        )


# ---------------------------------------------------------------------------
# AC: constant-order → scored DayLog.order_qty after case rounding
# (T-079: qty applies on OrderSchedule order days only; else forced 0)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_q", "case_size"),
    [
        (0, 8),
        (8, 8),
        (10, 8),  # nearest → 8 (was ceil → 16 before T-042)
        (16, 8),
        (1, 8),
    ],
)
def test_constant_order_policy_scored_order_qty_case_rounded(
    monkeypatch: pytest.MonkeyPatch,
    raw_q: int,
    case_size: int,
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    params = ModelParams(case_size=case_size)
    expected = _case_nearest_units(raw_q, case_size)
    policy = _ConstantOrderPolicy(raw_q)
    ep = _run_closed_loop(
        policy,
        shipments=ships,
        params=params,
        n_burn=2,
        n_score=5,
        root_seed=21,
        run_id=f"t024-q{raw_q}",
    )
    assert ep.scored, "expected scored days"
    for day in ep.scored:
        if _is_order_day(day.day):
            assert day.order_qty == expected, (
                f"order day={day.day} weekday={_weekday(day.day)}: "
                f"expected {expected}, got {day.order_qty}"
            )
            assert day.order_qty >= 0
            if expected > 0:
                assert day.order_qty % case_size == 0
        else:
            assert day.order_qty == 0, (
                f"non-order day={day.day} weekday={_weekday(day.day)}: "
                f"T-079 gate must force order_qty=0 (got {day.order_qty})"
            )


def test_constant_order_applies_on_burn_and_score_order_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-079 supersedes daily-ordering assumption: nonzero only on schedule days."""
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    policy = _ConstantOrderPolicy(8)
    ep = _run_closed_loop(
        policy,
        shipments=ships,
        n_burn=3,
        n_score=4,
        root_seed=5,
        run_id="t024-all-days",
    )
    assert len(policy.calls) == ep.n_burn + ep.n_score
    for day in ep.days:
        if _is_order_day(day.day):
            assert day.order_qty == 8, (
                f"order day={day.day}: expected policy qty 8, got {day.order_qty}"
            )
        else:
            assert day.order_qty == 0, (
                f"non-order day={day.day}: T-079 gate must force 0, got {day.order_qty}"
            )


# ---------------------------------------------------------------------------
# AC: SIM-05 CRN streams stable; unused stream draw does not desync
# ---------------------------------------------------------------------------


def test_closed_loop_crn_demand_alloc_spoil_stable_across_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    kwargs: dict[str, Any] = {
        "shipments": ships,
        "params": ModelParams(),
        "root_seed": 42,
        "run_id": "t024-crn",
        "n_burn": 3,
        "n_score": 7,
    }
    a = _run_closed_loop(_ConstantOrderPolicy(8), **kwargs)
    b = _run_closed_loop(_ConstantOrderPolicy(8), **kwargs)
    assert len(a.days) == len(b.days)
    for da, db in zip(a.days, b.days, strict=True):
        assert da.demand == db.demand
        assert da.sales_total == db.sales_total
        assert da.waste_total == db.waste_total
        assert da.arrivals == db.arrivals
        assert da.order_qty == db.order_qty


def test_extra_unused_stream_draw_does_not_change_demand_alloc_spoil_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding draws on an unused stream must not move demand/alloc/spoil slots."""
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    root_seed = 7
    run_id = "t024-unused"
    n_burn = 2
    n_score = 4

    baseline = _run_closed_loop(
        _ConstantOrderPolicy(8),
        shipments=ships,
        root_seed=root_seed,
        run_id=run_id,
        n_burn=n_burn,
        n_score=n_score,
    )

    # Consume an unrelated semantic stream before the second episode.
    unused = spawn_rng(root_seed, run_id=run_id, day=0, stream=STREAM_FILTER_RESAMPLE)
    _ = unused.random(500)

    perturbed = _run_closed_loop(
        _ConstantOrderPolicy(8),
        shipments=ships,
        root_seed=root_seed,
        run_id=run_id,
        n_burn=n_burn,
        n_score=n_score,
    )
    for da, db in zip(baseline.days, perturbed.days, strict=True):
        assert da.demand == db.demand
        assert da.sales_total == db.sales_total
        assert da.waste_total == db.waste_total
        assert da.arrivals == db.arrivals

    # Slot addressing still works for named physics streams.
    for day in range(n_burn + n_score):
        for stream in (
            STREAM_DEMAND,
            STREAM_ALLOC,
            STREAM_SPOIL,
            STREAM_ARRIVAL_SHIP,
            STREAM_ARRIVAL_SENSOR,
        ):
            a = spawn_rng(root_seed, run_id=run_id, day=day, stream=stream)
            b = spawn_rng(root_seed, run_id=run_id, day=day, stream=stream)
            assert np.array_equal(a.random(8), b.random(8))


# ---------------------------------------------------------------------------
# AC: SIM-03 burn-in / scored structure
# ---------------------------------------------------------------------------


def test_episode_exposes_n_burn_and_scored_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    n_burn, n_score = 4, 6
    ep = _run_closed_loop(
        _ConstantOrderPolicy(8),
        shipments=ships,
        n_burn=n_burn,
        n_score=n_score,
        root_seed=9,
        run_id="t024-burn",
    )
    assert ep.n_burn == n_burn
    assert ep.n_score == n_score
    assert len(ep.days) == n_burn + n_score
    assert len(ep.scored) == n_score
    assert ep.scored == ep.days[n_burn:]
    # Burn-in days remain in the log (discarded only for scoring consumers).
    assert ep.days[:n_burn]


def test_n_burn_zero_boundary_scored_is_full_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    ep = _run_closed_loop(
        _ConstantOrderPolicy(0),
        shipments=ships,
        n_burn=0,
        n_score=3,
        root_seed=2,
        run_id="t024-nb0",
    )
    assert ep.n_burn == 0
    assert len(ep.scored) == 3
    assert ep.scored == ep.days


# ---------------------------------------------------------------------------
# AC: no matplotlib / parquet writes in driver module
# ---------------------------------------------------------------------------


def _driver_module_paths() -> list[Path]:
    root = Path(sim_pkg.__file__).resolve().parent
    paths = [root / "__init__.py"]
    episode = root / "episode.py"
    if episode.is_file():
        paths.append(episode)
    return paths


def test_closed_loop_driver_module_has_no_matplotlib_or_parquet_imports() -> None:
    """Driver stays library-pure (M2 brief); figures/parquet stay outside."""
    forbidden = {"matplotlib", "pyarrow", "pyplot"}
    # Force resolution so implementers have created the entry surface.
    _ = _resolve_closed_loop_runner()
    found_driver = False
    for path in _driver_module_paths():
        if path.name == "episode.py":
            found_driver = True
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                assert name not in forbidden, (
                    f"{path} imports forbidden dependency {name!r}"
                )
    # If closed-loop lives only in sim/__init__.py, still checked above.
    _ = found_driver  # optional dedicated module


def test_closed_loop_does_not_write_figures_or_parquet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_abdella_fs_forbidden(monkeypatch)
    ships = _fixture_shipments()
    before = {p.name for p in tmp_path.iterdir()} if tmp_path.exists() else set()
    monkeypatch.chdir(tmp_path)
    _run_closed_loop(
        _ConstantOrderPolicy(8),
        shipments=ships,
        n_burn=1,
        n_score=2,
        root_seed=4,
        run_id="t024-no-write",
    )
    after = {p.name for p in tmp_path.iterdir()}
    created = after - before
    assert not any(
        name.endswith((".png", ".pdf", ".parquet", ".md")) for name in created
    ), f"driver wrote artifact files: {created}"
