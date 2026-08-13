"""T-082 CAL-B3 — DemandModel + draw_demand(day=) (RED).

Locks ADR 0110 / 0112 / 0113 and ``.team/specs/T-082.md``:

* ``draw_demand(rng, params, *, day=None)`` — day+profile → μ(day); day None →
  prior ``demand_mu`` compat (A2 shim)
* ``load_demand_profile`` reads committed JSON only (no HF / ``datasets``)
* ``day_step`` uses day-indexed demand when day/profile supplied
* distinct weekdays with distinct profile means → distinct μ
* package import graph still excludes HF / ``datasets``
* A2 shim call sites (no ``day=`` / ``day=None``) remain collectable/green

Offline only — assert against committed ``data/freshnet/demand_profile.json``.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi import model as model_pkg
from blueberries_voi.model import Cohort, ModelParams, day_step, draw_demand
from blueberries_voi.rng import STREAM_ALLOC, STREAM_DEMAND, STREAM_SPOIL, spawn_rng

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMAND_PROFILE_PATH = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

_FORBIDDEN_RUNTIME_IMPORT_ROOTS = frozenset(
    {
        "datasets",
        "huggingface_hub",
        "huggingface_hub.hf_api",
        "huggingface",
    }
)

# Committed product notes: μ(day) = scale * dow[day%7] * week[day//7]
# (monday0; week clamped to available factors).
_N_SAMPLES = 4000
_MEAN_ABS_TOL = 2.5  # seeded NB mean vs analytic μ


def _load_raw_profile() -> dict[str, Any]:
    assert _DEMAND_PROFILE_PATH.is_file(), (
        "committed data/freshnet/demand_profile.json required (T-080 / T-082)"
    )
    raw = json.loads(_DEMAND_PROFILE_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _expected_mu(day: int, raw: dict[str, Any] | None = None) -> float:
    """Reference μ(day) from committed JSON (notes / ADR 0112 scale x DOW x week)."""
    data = raw if raw is not None else _load_raw_profile()
    scale = float(data["scale_target_mu"])
    dow_factors = [float(x) for x in data["dow_factors"]]
    week_factors = [float(x) for x in data["week_factors"]]
    assert len(dow_factors) == 7
    assert len(week_factors) >= 1
    dow = int(day) % 7
    week = min(int(day) // 7, len(week_factors) - 1)
    return scale * dow_factors[dow] * week_factors[week]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _demand_api_module() -> Any:
    """Resolve model or model.demand* module exporting load_demand_profile."""
    candidates = (
        "blueberries_voi.model",
        "blueberries_voi.model.demand",
        "blueberries_voi.model.demand_profile",
        "blueberries_voi.model.demand_model",
    )
    seen: list[str] = []
    for name in candidates:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            seen.append(f"{name} (missing)")
            continue
        seen.append(name)
        if hasattr(mod, "load_demand_profile"):
            return mod
    pytest.fail(
        "load_demand_profile must be importable from blueberries_voi.model "
        "or model.demand* (ADR 0113 Track B); tried: " + ", ".join(seen)
    )


def _require_attr(obj: Any, name: str) -> Any:
    assert hasattr(obj, name), (
        f"{getattr(obj, '__name__', type(obj).__name__)} must expose {name!r} "
        "(T-082 / ADR 0113)"
    )
    return getattr(obj, name)


def _params_with_profile(profile: Any, **kwargs: Any) -> ModelParams:
    """Attach loaded profile to ModelParams (field name left to implementer)."""
    base = ModelParams(**kwargs)
    field_names = {f.name for f in getattr(base, "__dataclass_fields__", {}).values()}
    candidates = (
        "demand_profile",
        "profile",
        "calendar_demand",
        "demand_model",
    )
    for name in candidates:
        if name in field_names:
            return ModelParams(**{**kwargs, name: profile})
    # Factory / companion attach if present on model or demand* module.
    for mod in (model_pkg,):
        attach = getattr(mod, "with_demand_profile", None)
        if callable(attach):
            return attach(base, profile)  # type: ignore[no-any-return]
    for mod_name in (
        "blueberries_voi.model.demand",
        "blueberries_voi.model.demand_profile",
        "blueberries_voi.model.demand_model",
    ):
        loaded: types.ModuleType | None = sys.modules.get(mod_name)
        if loaded is None:
            continue
        attach = getattr(loaded, "with_demand_profile", None)
        if callable(attach):
            return attach(base, profile)  # type: ignore[no-any-return]
    msg = (
        "ModelParams must carry a loaded demand profile "
        f"(tried fields {candidates} and with_demand_profile); "
        f"fields present: {sorted(field_names)}"
    )
    raise AssertionError(msg)


def _mu_accessor(profile: Any, params: ModelParams) -> Any:
    """Resolve a direct μ(day) accessor when available."""
    objs: list[Any] = [profile, params, model_pkg]
    for name in (
        "blueberries_voi.model.demand",
        "blueberries_voi.model.demand_profile",
        "blueberries_voi.model.demand_model",
    ):
        mod = sys.modules.get(name)
        if mod is not None:
            objs.append(mod)
    for obj in objs:
        for attr in (
            "mu",
            "mu_for_day",
            "mean",
            "demand_mu",
            "mean_for_day",
            "demand_mu_for_day",
            "calendar_demand_mu",
        ):
            fn = getattr(obj, attr, None)
            if callable(fn):
                return fn
    return None


def _resolve_mu(day: int, profile: Any, params: ModelParams) -> float:
    accessor = _mu_accessor(profile, params)
    if accessor is None:
        pytest.fail(
            "DemandProfile / ModelParams must expose a μ(day) accessor "
            "(e.g. profile.mu(day) or demand_mu_for_day) for T-082 AC"
        )
    # Bound method vs free function taking (params, day) / (day,).
    try:
        return float(accessor(day))
    except TypeError:
        try:
            return float(accessor(params, day))
        except TypeError:
            return float(accessor(day=day))


# ---------------------------------------------------------------------------
# AC: draw_demand(rng, params, *, day=None) signature + μ behaviour
# ---------------------------------------------------------------------------


def test_draw_demand_signature_is_keyword_only_day_optional() -> None:
    """Public signature: draw_demand(rng, params, *, day: int | None = None)."""
    sig = inspect.signature(draw_demand)
    assert "day" in sig.parameters, (
        "draw_demand must accept keyword-only day= (ADR 0113 / T-082); "
        f"parameters={list(sig.parameters)}"
    )
    param = sig.parameters["day"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
        "day must be keyword-only (*, day=...) per ADR 0113"
    )
    assert param.default is None, "day default must be None for A2 compat shim"


def test_draw_demand_day_none_without_profile_matches_prior_demand_mu() -> None:
    """Compat: day=None and no profile → constant demand_mu NB (pre-CAL)."""
    sig = inspect.signature(draw_demand)
    assert "day" in sig.parameters, (
        "draw_demand must accept day= before compat behaviour can be asserted"
    )
    params = ModelParams(demand_mu=30.0, demand_vm=2.0)
    rng = spawn_rng(99, run_id="t082-compat", day=0, stream=STREAM_DEMAND)
    samples = [draw_demand(rng, params, day=None) for _ in range(_N_SAMPLES)]
    mean = float(np.mean(samples))
    assert abs(mean - params.demand_mu) < _MEAN_ABS_TOL, (
        f"day=None without profile must match prior demand_mu={params.demand_mu}; "
        f"got sample mean {mean}"
    )


def test_draw_demand_with_day_and_profile_uses_profile_mu() -> None:
    """When day is set and a profile is configured, NB mean equals μ(day)."""
    demand_api = _demand_api_module()
    loader = _require_attr(demand_api, "load_demand_profile")
    profile = loader(_DEMAND_PROFILE_PATH)
    params = _params_with_profile(profile, demand_mu=30.0, demand_vm=2.0)
    day = 6  # Sunday under monday0 — high weekend factor in committed JSON
    expected = _expected_mu(day)
    # Prefer direct accessor when present; also check draw mean.
    accessor = _mu_accessor(profile, params)
    if accessor is not None:
        assert abs(_resolve_mu(day, profile, params) - expected) < 1e-6

    assert "day" in inspect.signature(draw_demand).parameters
    rng = spawn_rng(7, run_id="t082-mu", day=day, stream=STREAM_DEMAND)
    samples = [draw_demand(rng, params, day=day) for _ in range(_N_SAMPLES)]
    mean = float(np.mean(samples))
    assert abs(mean - expected) < _MEAN_ABS_TOL, (
        f"draw_demand(..., day={day}) mean {mean} must track profile μ={expected}"
    )


# ---------------------------------------------------------------------------
# AC: loader JSON-only for demand_profile.json (no HF)
# ---------------------------------------------------------------------------


def test_load_demand_profile_reads_committed_json_without_freshnet_extra() -> None:
    demand_api = _demand_api_module()
    loader = _require_attr(demand_api, "load_demand_profile")
    profile_type = getattr(demand_api, "DemandProfile", None) or getattr(
        model_pkg, "DemandProfile", None
    )
    assert profile_type is not None, (
        "model must export DemandProfile (T-082 interfaces)"
    )

    before = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }

    profile = loader(_DEMAND_PROFILE_PATH)
    assert isinstance(profile, profile_type)

    after = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }
    newly = after - before
    assert not newly, (
        "load_demand_profile must be JSON-only; must not load HF/datasets "
        f"modules; newly loaded {sorted(newly)}"
    )


def test_load_demand_profile_source_has_no_hf_imports() -> None:
    """Static: demand loader module(s) must not import datasets / HF."""
    # Require the symbol so this is not a vacuous pass pre-implement.
    _demand_api_module()
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "load_demand_profile" not in text and "DemandProfile" not in text:
            continue
        hit = _imported_roots(path) & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
        if hit:
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{sorted(hit)}")
    assert not offenders, (
        f"demand profile loader sources must not import HF/datasets; found {offenders}"
    )


# ---------------------------------------------------------------------------
# AC: day_step uses day-indexed demand when day/profile supplied
# ---------------------------------------------------------------------------


def test_day_step_uses_day_indexed_demand_when_day_and_profile_supplied() -> None:
    """CRN / episode can supply episode day; demand follows profile μ(day).

    Implementer may put ``day=`` on ``day_step`` or pre-draw via
    ``draw_demand(..., day=)`` (spec open question); either path must yield
    day-indexed demand when a profile is configured.
    """
    demand_api = _demand_api_module()
    loader = _require_attr(demand_api, "load_demand_profile")
    profile = loader(_DEMAND_PROFILE_PATH)
    params = _params_with_profile(profile, demand_mu=30.0, demand_vm=2.0)
    day = 5  # Saturday
    expected = _expected_mu(day)

    sig = inspect.signature(day_step)
    # Signature must allow day= *or* callers must be able to pass day into
    # draw_demand (already locked elsewhere). Prefer day_step day= when present.
    demands: list[int] = []
    for i in range(_N_SAMPLES):
        rng_d = spawn_rng(1000 + i, run_id="t082-ds", day=day, stream=STREAM_DEMAND)
        rng_a = spawn_rng(1000 + i, run_id="t082-ds", day=day, stream=STREAM_ALLOC)
        rng_s = spawn_rng(1000 + i, run_id="t082-ds", day=day, stream=STREAM_SPOIL)
        cohorts = [Cohort(n=200, tau=1.0, lot_id=1)]
        if "day" in sig.parameters:
            result = day_step(
                cohorts,
                params=params,
                demand=None,
                day=day,
                rng_demand=rng_d,
                rng_alloc=rng_a,
                rng_spoil=rng_s,
                delivery=None,
            )
        else:
            # Equivalent wiring: CRN draws with day=, passes demand into day_step.
            assert "day" in inspect.signature(draw_demand).parameters, (
                "without day_step(day=), draw_demand must accept day= so CRN "
                "can pass episode day (T-082 / ADR 0113)"
            )
            demand = draw_demand(rng_d, params, day=day)
            result = day_step(
                cohorts,
                params=params,
                demand=demand,
                rng_demand=rng_d,
                rng_alloc=rng_a,
                rng_spoil=rng_s,
                delivery=None,
            )
        demands.append(int(result.demand))

    mean = float(np.mean(demands))
    assert abs(mean - expected) < _MEAN_ABS_TOL, (
        f"day-indexed day_step demand mean {mean} must track μ={expected}"
    )


# ---------------------------------------------------------------------------
# AC: different weekdays → different μ
# ---------------------------------------------------------------------------


def test_distinct_weekdays_with_distinct_profile_means_differ() -> None:
    demand_api = _demand_api_module()
    loader = _require_attr(demand_api, "load_demand_profile")
    profile = loader(_DEMAND_PROFILE_PATH)
    params = _params_with_profile(profile, demand_mu=30.0, demand_vm=2.0)

    # Thursday (low) vs Sunday (high) in committed dow_factors.
    day_lo, day_hi = 3, 6
    mu_lo = _expected_mu(day_lo)
    mu_hi = _expected_mu(day_hi)
    assert mu_lo != mu_hi, "fixture profile must have distinct weekday means"

    got_lo = _resolve_mu(day_lo, profile, params)
    got_hi = _resolve_mu(day_hi, profile, params)
    assert got_lo != got_hi
    assert abs(got_lo - mu_lo) < 1e-6
    assert abs(got_hi - mu_hi) < 1e-6
    assert got_hi > got_lo


# ---------------------------------------------------------------------------
# AC: package import graph still excludes datasets / HF
# ---------------------------------------------------------------------------


def test_package_import_graph_excludes_datasets_and_hf() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        hit = _imported_roots(path) & _FORBIDDEN_RUNTIME_IMPORT_ROOTS
        if hit:
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{sorted(hit)}")
    assert not offenders, (
        "installable blueberries_voi sources must not import HF/datasets "
        f"(ADR 0112 / T-082); found {offenders}"
    )


def test_importing_model_does_not_load_datasets_or_huggingface() -> None:
    doomed = [
        key
        for key in list(sys.modules)
        if key == "blueberries_voi" or key.startswith("blueberries_voi.")
    ]
    for key in doomed:
        del sys.modules[key]

    before = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }

    importlib.import_module("blueberries_voi.model")
    # Touch demand API if present (must stay HF-free).
    mod = importlib.import_module("blueberries_voi.model")
    loader = getattr(mod, "load_demand_profile", None)
    if callable(loader) and _DEMAND_PROFILE_PATH.is_file():
        loader(_DEMAND_PROFILE_PATH)

    after = {
        key
        for key in sys.modules
        if key == "datasets"
        or key.startswith("datasets.")
        or key == "huggingface_hub"
        or key.startswith("huggingface_hub.")
        or key == "huggingface"
        or key.startswith("huggingface.")
    }
    newly = after - before
    assert not newly, (
        "importing blueberries_voi.model (+ load_demand_profile) must not load "
        f"datasets/HF; newly loaded {sorted(newly)}"
    )


# ---------------------------------------------------------------------------
# AC: A2 shim tests remain collectable / green where applicable
# ---------------------------------------------------------------------------


def test_a2_shim_positional_draw_demand_still_callable() -> None:
    """Pre-T-082 / A2 call sites: draw_demand(rng, params) without day=."""
    params = ModelParams(demand_mu=30.0, demand_vm=2.0)
    rng = spawn_rng(42, run_id="t082-shim", day=0, stream=STREAM_DEMAND)
    value = draw_demand(rng, params)
    assert isinstance(value, int)
    assert value >= 0


def test_a2_shim_draw_demand_day_default_preserves_constant_mu_nb() -> None:
    """Omitting day= (A2 shim) must keep pre-CAL constant demand_mu behaviour."""
    params = ModelParams(demand_mu=30.0, demand_vm=2.0)
    rng = spawn_rng(99, run_id="t082-shim-mean", day=1, stream=STREAM_DEMAND)
    samples = [draw_demand(rng, params) for _ in range(_N_SAMPLES)]
    mean = float(np.mean(samples))
    assert 20.0 < mean < 40.0
    assert abs(mean - params.demand_mu) < _MEAN_ABS_TOL
