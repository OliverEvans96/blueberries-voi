"""T-030 CTL-02/04 one-step rollout + salvage V_T -- RED acceptance contracts.

Locks ADR 0059 (CTL-02=B single-step rollout), ADR 0061 (CTL-04=B H ~ 2x shelf
life + survival-weighted terminal salvage), ENG-04 CRN pairing prep, and
``.team/specs/T-030.md`` before production rollout code exists.

Fixture locks (frozen here + ``.team/qa/T-030.md``):

* ``H_default = 2 * ModelParams().eta_ref`` -> **28** (eta_ref=14)
* Candidate neighbourhood: case multiples within +/-2 cases of base ``q_t``
* Paired-CRN profit seeds: ``root_seeds=(11, 22, 33)``, run_id prefix ``t030-crn``
* Profit >= tolerance: absolute **1e-6** (improvement or tie)
* ``V_T = m * sum_l w_long(tau_l) * n_l``; ``w_long`` from oldest-first queue
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi import model as model_pkg
from blueberries_voi.controller.damped_sw import DampedSurvivalWeightedPolicy
from blueberries_voi.filter.belief import shelf_belief_from_oracle
from blueberries_voi.model import ModelParams, day_step
from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.rng import STREAM_DEMAND, STREAM_SPOIL, spawn_rng
from blueberries_voi.sim.profit import ProfitCosts, episode_profit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROLLER_PKG = "blueberries_voi.controller"
_ROLLOUT_ATTR = "rollout_order"
_ROLLOUT_MODULE_CANDIDATES = (
    "blueberries_voi.controller.rollout",
    "blueberries_voi.controller",
)

# --- Fixture locks (see module docstring / QA artifact) ---
_ETA_REF = float(ModelParams().eta_ref)  # 14.0
_H_DEFAULT = int(2 * _ETA_REF)  # 28
_CANDIDATE_CASE_RADIUS = 2
_CRN_ROOT_SEEDS: tuple[int, ...] = (11, 22, 33)
_CRN_RUN_ID_PREFIX = "t030-crn"
_PROFIT_ABS_TOL = 1e-6
_VT_FORMULA_LOCK = "V_T = m * sum_l w_long(tau_l) * n_l"

_FORBIDDEN_IMPORT_ROOTS = frozenset({"matplotlib", "pyplot", "pyarrow"})
_FORBIDDEN_WRITE_ATTRS = frozenset(
    {"write_text", "write_bytes", "mkdir", "touch", "dump", "savefig"}
)
_PARALLEL_IMPORT_ROOTS = frozenset({"multiprocessing"})
_PARALLEL_NAME_FRAGMENTS = frozenset(
    {"ProcessPoolExecutor", "Pool", "Process", "multiprocessing"}
)

_TABLE_GRID = (0.0, 2.0, 4.0, 6.0)
_DEFAULT_COSTS = ProfitCosts(unit_margin=2.0, waste_cost=1.5, stockout_penalty=3.0)


def _resolve_rollout_module() -> Any:
    """Locate the controller rollout module that exports ``rollout_order``."""
    last_err: Exception | None = None
    for name in _ROLLOUT_MODULE_CANDIDATES:
        try:
            mod = importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
        if getattr(mod, _ROLLOUT_ATTR, None) is not None:
            return mod
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        f"{_ROLLOUT_ATTR} must be exported from controller "
        f"(tried {_ROLLOUT_MODULE_CANDIDATES}) per T-030 / ADR 0059{detail}",
        pytrace=False,
    )


def _resolve(attr: str) -> Any:
    mod = _resolve_rollout_module()
    found = getattr(mod, attr, None)
    if found is None:
        pytest.fail(
            f"{attr} must be exported from {mod.__name__} (T-030 / ADR 0061)",
            pytrace=False,
        )
    return found


def _rollout_defining_module() -> Any:
    fn = _resolve(_ROLLOUT_ATTR)
    return importlib.import_module(fn.__module__)


def _rollout_source_path() -> Path:
    mod = _rollout_defining_module()
    path = Path(inspect.getsourcefile(mod) or "")
    assert path.is_file(), f"missing source for {mod.__name__}"
    return path


def _fixture_shipments() -> list[ShipmentTrace]:
    times = np.asarray([0.0, 1.0, 2.0], dtype=float)
    cool = np.asarray([1.0, 1.0, 1.0], dtype=float)
    warm = np.asarray([5.0, 5.0, 5.0], dtype=float)
    return [
        ShipmentTrace(
            shipment_id="T030-COOL",
            times_d=times,
            temps_c=cool,
            duration_d=2.0,
        ),
        ShipmentTrace(
            shipment_id="T030-WARM",
            times_d=times,
            temps_c=warm,
            duration_d=2.0,
        ),
    ]


def _table_belief(params: ModelParams | None = None) -> Any:
    del params  # belief construction does not need params for oracle fixtures
    return shelf_belief_from_oracle(
        lot_counts=[20, 10],
        ages=[0.0, 4.0],
        tau_grid=list(_TABLE_GRID),
    )


def _resolve_closed_loop() -> Callable[..., Any]:
    for mod_name in ("blueberries_voi.sim.episode", "blueberries_voi.sim"):
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            continue
        fn = getattr(mod, "run_closed_loop_episode", None)
        if callable(fn):
            return fn
    pytest.fail(
        "run_closed_loop_episode required for T-030 profit CRN comparison",
        pytrace=False,
    )


def _mean_episode_profit(
    policy: Any,
    *,
    root_seeds: Sequence[int],
    run_id_prefix: str,
    params: ModelParams,
    n_burn: int = 2,
    n_score: int = 5,
) -> float:
    runner = _resolve_closed_loop()
    ships = _fixture_shipments()
    profits: list[float] = []
    for seed in root_seeds:
        episode = runner(
            policy,
            shipments=ships,
            params=params,
            root_seed=int(seed),
            run_id=f"{run_id_prefix}-{seed}",
            n_burn=n_burn,
            n_score=n_score,
            lead_time=1,
        )
        profits.append(float(episode_profit(episode, _DEFAULT_COSTS)))
    return float(sum(profits) / len(profits))


def _candidate_orders(base_q: int, case_size: int, radius: int) -> list[int]:
    """Multiples of case_size within ±radius cases of base_q (inclusive)."""
    base_cases = base_q // case_size
    out: list[int] = []
    for dc in range(-radius, radius + 1):
        q = (base_cases + dc) * case_size
        if q >= 0:
            out.append(q)
    return out


# ---------------------------------------------------------------------------
# AC: rollout_order export + one improvement step / H / V_T documentation
# ---------------------------------------------------------------------------


def test_rollout_order_is_exportable() -> None:
    fn = _resolve(_ROLLOUT_ATTR)
    assert callable(fn)
    assert fn.__name__ == _ROLLOUT_ATTR


def test_rollout_order_signature_matches_spec_sketch() -> None:
    fn = _resolve(_ROLLOUT_ATTR)
    sig = inspect.signature(fn)
    names = list(sig.parameters)
    assert names, "rollout_order must accept belief as first argument"
    assert names[0] == "belief"
    for required in ("base_policy", "params", "rng_address"):
        assert required in sig.parameters, f"missing keyword-only {required}"
        assert sig.parameters[required].kind is inspect.Parameter.KEYWORD_ONLY
    assert "H" in sig.parameters
    assert "n_rollout_paths" in sig.parameters


def test_default_horizon_is_twice_eta_ref() -> None:
    """CTL-04=B: H ~ 2x shelf life; lock H_default = 2 * eta_ref = 28."""
    params = ModelParams()
    assert float(params.eta_ref) == pytest.approx(_ETA_REF)
    assert _H_DEFAULT == 28

    fn = _resolve(_ROLLOUT_ATTR)
    h_default = inspect.signature(fn).parameters["H"].default
    if h_default is inspect.Parameter.empty:
        # Module-level constant is an acceptable desktop default surface.
        mod = _rollout_defining_module()
        h_default = getattr(mod, "DEFAULT_ROLLOUT_H", None)
        if h_default is None:
            h_default = getattr(mod, "DEFAULT_H", None)
    assert h_default is not None and h_default is not inspect.Parameter.empty
    assert int(h_default) == _H_DEFAULT


def test_candidate_neighbourhood_is_plus_minus_two_cases() -> None:
    """Freeze ±2 case neighbourhood around base q_t (spec open question)."""
    params = ModelParams()
    case_size = int(params.case_size)
    base_q = 24
    expected = _candidate_orders(base_q, case_size, _CANDIDATE_CASE_RADIUS)
    assert expected == [8, 16, 24, 32, 40]

    builder = getattr(_resolve_rollout_module(), "candidate_orders", None)
    if builder is None:
        builder = getattr(_rollout_defining_module(), "candidate_orders", None)
    assert callable(builder), (
        "export candidate_orders(base_q, *, case_size, radius=2) to freeze "
        "the CTL-02 neighbourhood (T-030 open question)"
    )
    got = builder(base_q, case_size=case_size, radius=_CANDIDATE_CASE_RADIUS)
    assert list(got) == expected
    # Non-negative case multiples only (base near zero clamps at 0).
    near_zero = list(builder(0, case_size=case_size, radius=_CANDIDATE_CASE_RADIUS))
    assert near_zero == [0, 8, 16]
    assert all(q >= 0 and q % case_size == 0 for q in near_zero)


def test_candidate_orders_rejects_empty_or_invalid() -> None:
    """Unhappy path: empty / invalid neighbourhood must not silently proceed."""
    builder = getattr(_resolve_rollout_module(), "candidate_orders", None)
    if builder is None:
        builder = getattr(_rollout_defining_module(), "candidate_orders", None)
    assert callable(builder), "candidate_orders must be exported (T-030)"

    with pytest.raises((ValueError, TypeError)):
        builder(24, case_size=8, radius=-1)

    # Explicit empty override on rollout_order (if supported) must fail loud.
    fn = _resolve(_ROLLOUT_ATTR)
    sig = inspect.signature(fn)
    if "candidates" in sig.parameters or "candidate_orders" in sig.parameters:
        params = ModelParams()
        belief = _table_belief(params)
        base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
        kw = "candidates" if "candidates" in sig.parameters else "candidate_orders"
        with pytest.raises((ValueError, TypeError)):
            fn(
                belief,
                base_policy=base,
                params=params,
                rng_address={
                    "root_seed": 11,
                    "run_id": f"{_CRN_RUN_ID_PREFIX}-empty-cands",
                },
                **{kw: ()},
            )


def test_rollout_order_rejects_nonpositive_horizon() -> None:
    """H=0 is not a meaningful forward horizon; H=1 remains a valid edge."""
    fn = _resolve(_ROLLOUT_ATTR)
    params = ModelParams()
    belief = _table_belief(params)
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
    rng_address = {"root_seed": 11, "run_id": f"{_CRN_RUN_ID_PREFIX}-h-edge"}

    with pytest.raises((ValueError, TypeError)):
        fn(
            belief,
            base_policy=base,
            params=params,
            rng_address=rng_address,
            H=0,
        )

    # H=1: one forward day + salvage — must return a legal case order.
    got = fn(
        belief,
        base_policy=base,
        params=params,
        rng_address=rng_address,
        H=1,
        n_rollout_paths=1,
    )
    assert isinstance(got, int)
    assert got >= 0
    assert got % params.case_size == 0


def test_terminal_salvage_vt_matches_margin_times_w_long_sum() -> None:
    """ADR 0061: V_T = m * sum_l w_long(tau_l) * n_l (oldest-first queue w_long)."""
    salvage = _resolve("terminal_salvage_value")
    assert callable(salvage)

    # Explicit lot table: oldest-first order by age; n and tau locked.
    lots = (
        {"n": 4, "tau": 6.0},
        {"n": 2, "tau": 2.0},
        {"n": 1, "tau": 0.0},
    )
    margin = 2.0  # m in ADR 0061
    params = ModelParams()

    # Implementation must expose w_long for the same lots so the product locks.
    w_long_fn = getattr(_rollout_defining_module(), "w_long_oldest_first", None)
    if w_long_fn is None:
        w_long_fn = getattr(_resolve_rollout_module(), "w_long_oldest_first", None)
    assert callable(w_long_fn), (
        "export w_long_oldest_first(...) so V_T = m * sum w_long * n is checkable"
    )
    weights = list(w_long_fn(lots, params=params))
    assert len(weights) == len(lots)
    expected = margin * sum(
        float(w) * float(lot["n"]) for w, lot in zip(weights, lots, strict=True)
    )
    got = float(salvage(lots, margin=margin, params=params))
    assert got == pytest.approx(expected, rel=0.0, abs=1e-12)


def test_terminal_salvage_empty_lots_is_zero() -> None:
    salvage = _resolve("terminal_salvage_value")
    assert float(salvage((), margin=2.0, params=ModelParams())) == 0.0
    assert float(salvage([], margin=2.0, params=ModelParams())) == 0.0


def test_rollout_module_documents_vt_formula_and_adr_0061() -> None:
    mod = _rollout_defining_module()
    source = _rollout_source_path().read_text(encoding="utf-8")
    doc = (mod.__doc__ or "") + "\n" + source
    doc_compact = " ".join(doc.split())
    assert "V_T" in doc or "V_T" in source
    assert "w_long" in doc or "w_long" in source
    assert "0061" in doc or "CTL-04" in doc or "salvage" in doc.lower()
    # Formula lock string (allow mild whitespace variants already normalised).
    assert "w_long" in doc_compact and "sum" in doc_compact.lower()
    assert _VT_FORMULA_LOCK.split("=")[0].strip() in source or "V_T" in source


def test_rollout_order_returns_nonnegative_case_multiple() -> None:
    fn = _resolve(_ROLLOUT_ATTR)
    params = ModelParams()
    belief = _table_belief(params)
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
    got = fn(
        belief,
        base_policy=base,
        params=params,
        rng_address={"root_seed": 11, "run_id": f"{_CRN_RUN_ID_PREFIX}-unit"},
    )
    assert isinstance(got, int)
    assert got >= 0
    assert got % params.case_size == 0


# ---------------------------------------------------------------------------
# AC: paired CRN → mean rollout profit ≥ base SW (tol)
# ---------------------------------------------------------------------------


def test_rollout_mean_profit_ge_base_sw_under_paired_crn() -> None:
    """Improvement or tie under shared CRN seeds; never worse beyond abs 1e-6."""
    params = ModelParams()
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)

    # Prefer a public RolloutPolicy; else a module helper that builds one.
    mod = _resolve_rollout_module()
    policy_cls = getattr(mod, "RolloutPolicy", None)
    if policy_cls is None:
        policy_cls = getattr(_rollout_defining_module(), "RolloutPolicy", None)
    assert policy_cls is not None, (
        "export RolloutPolicy wrapping rollout_order for closed-loop scoring "
        "(T-030 paired-CRN profit AC)"
    )
    rollout_policy = policy_cls(base_policy=base, params=params)

    base_mean = _mean_episode_profit(
        base,
        root_seeds=_CRN_ROOT_SEEDS,
        run_id_prefix=_CRN_RUN_ID_PREFIX,
        params=params,
    )
    rollout_mean = _mean_episode_profit(
        rollout_policy,
        root_seeds=_CRN_ROOT_SEEDS,
        run_id_prefix=_CRN_RUN_ID_PREFIX,
        params=params,
    )
    assert rollout_mean + _PROFIT_ABS_TOL >= base_mean, (
        f"rollout mean profit {rollout_mean} must be ≥ base {base_mean} "
        f"within abs tol {_PROFIT_ABS_TOL} on seeds {_CRN_ROOT_SEEDS}"
    )


# ---------------------------------------------------------------------------
# AC: optional compute-budget knobs with full desktop defaults
# ---------------------------------------------------------------------------


def test_rollout_order_budget_kwargs_have_desktop_defaults() -> None:
    fn = _resolve(_ROLLOUT_ATTR)
    params = inspect.signature(fn).parameters
    for name in ("n_rollout_paths", "H"):
        assert name in params, f"missing budget knob {name}"
        assert params[name].default is not inspect.Parameter.empty, (
            f"{name} must default to a full desktop value (M2 agent brief)"
        )
    # Candidate set size and/or particle/sample caps — at least one radius/size
    # knob and optionally a particle cap.
    has_candidate = any(
        n in params
        for n in ("candidate_case_radius", "candidate_set_size", "n_candidates")
    )
    assert has_candidate, (
        "expose candidate_case_radius / candidate_set_size / n_candidates "
        "with a desktop default"
    )
    has_particle = any(
        n in params for n in ("n_particles", "max_particles", "particle_cap")
    )
    # Particle/sample cap is optional in the AC ("and/or"); if present it must
    # have a default.
    if has_particle:
        for n in ("n_particles", "max_particles", "particle_cap"):
            if n in params:
                assert params[n].default is not inspect.Parameter.empty


def test_omitting_budget_kwargs_preserves_production_behaviour() -> None:
    """Omitting optional budgets must match calling with the documented defaults."""
    fn = _resolve(_ROLLOUT_ATTR)
    params = ModelParams()
    belief = _table_belief(params)
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
    rng_address = {"root_seed": 22, "run_id": f"{_CRN_RUN_ID_PREFIX}-budget"}

    omitted = fn(
        belief,
        base_policy=base,
        params=params,
        rng_address=rng_address,
    )
    sig = inspect.signature(fn)
    explicit_kwargs: dict[str, Any] = {}
    for name in (
        "H",
        "n_rollout_paths",
        "candidate_case_radius",
        "candidate_set_size",
        "n_candidates",
        "n_particles",
        "max_particles",
        "particle_cap",
    ):
        if name in sig.parameters and sig.parameters[name].default is not (
            inspect.Parameter.empty
        ):
            explicit_kwargs[name] = sig.parameters[name].default
    explicit = fn(
        belief,
        base_policy=base,
        params=params,
        rng_address=rng_address,
        **explicit_kwargs,
    )
    assert omitted == explicit


# ---------------------------------------------------------------------------
# AC: forward steps share model.day_step (no shadow dynamics)
# ---------------------------------------------------------------------------


def test_rollout_forward_steps_use_shared_model_day_step() -> None:
    """ENG-02 / M2 brief: rollout forward path is identity-bound to model.day_step."""
    mod = _rollout_defining_module()
    bound = getattr(mod, "day_step", None)
    if bound is not None:
        assert bound is model_pkg.day_step
        assert bound is day_step

    source_path = _rollout_source_path()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    imports_day_step = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = {alias.name for alias in node.names}
            if "day_step" in names and (
                node.module == "blueberries_voi.model"
                or node.module.startswith("blueberries_voi.model")
                or node.module == "blueberries_voi"
            ):
                imports_day_step = True
        if isinstance(node, ast.Attribute) and node.attr == "day_step":
            imports_day_step = True
    assert imports_day_step, (
        f"{source_path.name} must call shared model.day_step (no shadow dynamics)"
    )

    # Reject a local def day_step that would shadow the shared kernel.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "day_step":
            pytest.fail(
                "rollout must not define a local day_step shadow",
                pytrace=False,
            )


def test_rollout_forward_steps_call_day_step_via_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioural identity: forward sims call shared model.day_step."""
    mod = _rollout_defining_module()
    calls: list[int] = []
    real = model_pkg.day_step

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    # Patch the shared symbol and any module-local binding (identity must hold).
    monkeypatch.setattr(model_pkg, "day_step", _spy)
    if getattr(mod, "day_step", None) is not None:
        monkeypatch.setattr(mod, "day_step", _spy)

    fn = _resolve(_ROLLOUT_ATTR)
    params = ModelParams()
    belief = _table_belief(params)
    base = DampedSurvivalWeightedPolicy(rho=0.8, alpha=0.9, params=params)
    order = fn(
        belief,
        base_policy=base,
        params=params,
        rng_address={"root_seed": 33, "run_id": f"{_CRN_RUN_ID_PREFIX}-day-step"},
        H=1,
        n_rollout_paths=1,
    )
    assert isinstance(order, int)
    assert order >= 0
    assert sum(calls) >= 1, (
        "rollout forward path must call model.day_step at least once "
        "(no shadow dynamics)"
    )


# ---------------------------------------------------------------------------
# AC: sequential rollouts (no multiprocessing / process pools)
# ---------------------------------------------------------------------------


def test_rollout_module_is_sequential_no_multiprocessing() -> None:
    source_path = _rollout_source_path()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in _PARALLEL_IMPORT_ROOTS, (
                    f"{source_path.name} must not import {alias.name} "
                    "(M2 brief: sequential rollouts)"
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in _PARALLEL_IMPORT_ROOTS, (
                f"{source_path.name} must not import from {node.module}"
            )
            for alias in node.names:
                assert alias.name not in _PARALLEL_NAME_FRAGMENTS, (
                    f"{source_path.name} must not import {alias.name} from "
                    f"{node.module}"
                )

    for frag in ("multiprocessing", "ProcessPoolExecutor", "multiprocess"):
        assert frag not in source, (
            f"{source_path.name} must not reference {frag} (sequential only)"
        )


# ---------------------------------------------------------------------------
# AC: CRN desync detector (ENG-04 prep)
# ---------------------------------------------------------------------------


def test_crn_desync_detector_passes_when_addressing_correct() -> None:
    """Detector API: correctly paired same-slot streams → ok / pass."""
    detect = _resolve("detect_crn_desync")
    assert callable(detect)

    root_seed = 11
    run_id = f"{_CRN_RUN_ID_PREFIX}-sync"
    day = 0
    # Identical SIM-05 addresses → paired CRN.
    result = detect(
        address_a={
            "root_seed": root_seed,
            "run_id": run_id,
            "day": day,
            "stream": STREAM_DEMAND,
        },
        address_b={
            "root_seed": root_seed,
            "run_id": run_id,
            "day": day,
            "stream": STREAM_DEMAND,
        },
        n_draws=32,
    )
    ok = getattr(result, "ok", None)
    if ok is None and isinstance(result, Mapping):
        ok = result.get("ok", result.get("passed"))
    if ok is None and isinstance(result, bool):
        ok = result
    assert ok is True, f"correct CRN addressing must report ok/pass, got {result!r}"

    # Sanity: the underlying streams really match when addresses match.
    a = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
    b = spawn_rng(root_seed, run_id=run_id, day=day, stream=STREAM_DEMAND)
    assert np.array_equal(a.random(8), b.random(8))


def test_crn_desync_detector_fails_when_streams_intentionally_crossed() -> None:
    """Detector API: crossed streams (demand vs spoil) → fail / desync."""
    detect = _resolve("detect_crn_desync")
    root_seed = 11
    run_id = f"{_CRN_RUN_ID_PREFIX}-cross"
    day = 0
    result = detect(
        address_a={
            "root_seed": root_seed,
            "run_id": run_id,
            "day": day,
            "stream": STREAM_DEMAND,
        },
        address_b={
            "root_seed": root_seed,
            "run_id": run_id,
            "day": day,
            "stream": STREAM_SPOIL,
        },
        n_draws=32,
    )
    ok = getattr(result, "ok", None)
    status = getattr(result, "status", None)
    if ok is None and isinstance(result, Mapping):
        ok = result.get("ok", result.get("passed"))
        status = result.get("status")
    if ok is None and isinstance(result, bool):
        ok = result
    assert ok is False, f"crossed CRN streams must report fail/desync, got {result!r}"
    if status is not None:
        assert str(status).lower() in {"desync", "fail", "failed", "error"}


# ---------------------------------------------------------------------------
# AC: controller/ free of figure / FS writers
# ---------------------------------------------------------------------------


def test_rollout_module_has_no_figure_or_fs_writers() -> None:
    """controller rollout stays a pure library (M2 agent brief)."""
    _ = _resolve(_ROLLOUT_ATTR)
    source_path = _rollout_source_path()
    assert "controller" in source_path.parts
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            imported.add(root)
            imported.add(node.module)
    forbidden = imported & _FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"{source_path.name} imports forbidden: {sorted(forbidden)}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                # Allow open-for-read only if mode is explicitly read-only; ban
                # bare open(...) and write modes in controller rollout.
                if len(node.args) >= 2:
                    mode_node = node.args[1]
                    if isinstance(mode_node, ast.Constant) and str(
                        mode_node.value
                    ).startswith("r"):
                        continue
                pytest.fail(
                    f"{source_path.name} must not open files for write",
                    pytrace=False,
                )
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_WRITE_ATTRS:
                pytest.fail(
                    f"{source_path.name} must not write files ({func.attr})",
                    pytrace=False,
                )


def test_controller_package_exports_rollout_order() -> None:
    fn = _resolve(_ROLLOUT_ATTR)
    pkg = importlib.import_module(_CONTROLLER_PKG)
    exported = getattr(pkg, "__all__", None)
    assert isinstance(exported, list)
    assert _ROLLOUT_ATTR in exported
    assert getattr(pkg, _ROLLOUT_ATTR, None) is fn
