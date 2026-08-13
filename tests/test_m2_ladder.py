"""T-032 CTL-05 five-point ladder - expected RED until ``run_m2_ladder`` lands.

Locks the M2 ladder harness: constant -> Rung 0 -> SW -> SW+rollout -> toy DP,
T-029 tuned-alpha gate before profit claims, numeric artifacts under
``experiments/`` and/or ``figures/m2/`` (never inside ``controller/``), and
production ``mean_field`` backend. See ``.team/specs/T-032.md``.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTROLLER_DIR = _REPO_ROOT / "src" / "blueberries_voi" / "controller"

_LADDER_MODULE_CANDIDATES: tuple[str, ...] = (
    "blueberries_voi.sim.m2_ladder",
    "blueberries_voi.viz.m2_ladder",
)

_FIVE_POINTS: tuple[str, ...] = (
    "constant",
    "rung0",
    "sw",
    "rollout",
    "dp",
)

_FORBIDDEN_CONTROLLER_IMPORTS = frozenset({"matplotlib", "pyplot", "pyarrow"})
_LOCKED_RUNTIME_DEPS = frozenset({"numpy", "scipy"})  # ADR 0101 / T-046 slim core


def _resolve_ladder_module() -> Any:
    errors: list[str] = []
    for name in _LADDER_MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
    pytest.fail(
        "T-032 requires run_m2_ladder module "
        f"(tried {list(_LADDER_MODULE_CANDIDATES)}): {'; '.join(errors)}",
        pytrace=False,
    )


def _resolve(attr: str) -> Any:
    mod = _resolve_ladder_module()
    found = getattr(mod, attr, None)
    if found is not None:
        return found
    # Allow re-export from sim package root once the module exists.
    try:
        sim = importlib.import_module("blueberries_voi.sim")
    except ImportError:
        sim = None
    if sim is not None:
        found = getattr(sim, attr, None)
        if found is not None:
            return found
    pytest.fail(
        f"{attr} must be exported from {_LADDER_MODULE_CANDIDATES[0]} "
        "(see .team/specs/T-032.md Interfaces)",
        pytrace=False,
    )


def _write_minimal_alpha_table(path: Path) -> Path:
    """Use T-029 helpers when present; otherwise write a JSON table stub."""
    table = {arm: 0.8 for arm in _FIVE_POINTS}
    try:
        save = importlib.import_module(
            "blueberries_voi.sim.alpha_tune"
        ).save_tuned_alpha_table
        save(path, table)
    except (ImportError, AttributeError):
        import json

        path.write_text(json.dumps(table), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC: run_m2_ladder(*, alpha_table_path, root_seed, ...) -> LadderResult
# ---------------------------------------------------------------------------


def test_run_m2_ladder_is_exportable() -> None:
    fn = _resolve("run_m2_ladder")
    assert callable(fn)


def test_ladder_result_type_is_exportable() -> None:
    result_type = _resolve("LadderResult")
    assert result_type is not None


def test_run_m2_ladder_signature_requires_alpha_table_and_root_seed() -> None:
    fn = _resolve("run_m2_ladder")
    params = inspect.signature(fn).parameters
    assert "alpha_table_path" in params, (
        "run_m2_ladder must take keyword-only alpha_table_path (T-029 gate)"
    )
    assert params["alpha_table_path"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "root_seed" in params
    assert params["root_seed"].kind is inspect.Parameter.KEYWORD_ONLY


def test_run_m2_ladder_evaluates_five_ctl05_points(tmp_path: Path) -> None:
    """CTL-05=A: constant -> corrected age-blind -> SW -> SW+rollout -> toy DP."""
    fn = _resolve("run_m2_ladder")
    result_type = _resolve("LadderResult")
    alpha_path = _write_minimal_alpha_table(tmp_path / "tuned_alpha.json")

    result = fn(alpha_table_path=alpha_path, root_seed=42)
    assert isinstance(result, result_type)

    points = getattr(result, "points", None)
    if points is None:
        points = getattr(result, "arms", None)
    if points is None and isinstance(result, Mapping):
        points = result.get("points", result.get("arms"))
    assert points is not None, "LadderResult must expose points/arms"

    if isinstance(points, Mapping):
        ids = frozenset(str(k) for k in points)
    else:
        ids = frozenset(str(getattr(p, "arm_id", getattr(p, "id", p))) for p in points)
    missing = frozenset(_FIVE_POINTS) - ids
    assert not missing, f"ladder missing CTL-05 points: {sorted(missing)}"


def test_ladder_result_records_numeric_profit_per_point(tmp_path: Path) -> None:
    fn = _resolve("run_m2_ladder")
    alpha_path = _write_minimal_alpha_table(tmp_path / "tuned_alpha.json")
    result = fn(alpha_table_path=alpha_path, root_seed=7)

    profits = getattr(result, "profits", None)
    if profits is None:
        profits = getattr(result, "arm_profits", None)
    if profits is None and isinstance(result, Mapping):
        profits = result.get("profits", result.get("arm_profits"))
    assert isinstance(profits, Mapping), (
        "LadderResult must expose a mapping of arm_id -> numeric profit"
    )
    for arm in _FIVE_POINTS:
        assert arm in profits, f"missing profit for arm {arm!r}"
        val = float(profits[arm])
        assert val == val  # not NaN


# ---------------------------------------------------------------------------
# AC: tuned alpha required before ladder profit claims
# ---------------------------------------------------------------------------


def test_run_m2_ladder_fails_when_tuned_alpha_artifact_missing(
    tmp_path: Path,
) -> None:
    fn = _resolve("run_m2_ladder")
    missing = tmp_path / "does-not-exist-tuned_alpha.json"
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError, AssertionError)):
        fn(alpha_table_path=missing, root_seed=0)


def test_run_m2_ladder_fails_when_alpha_table_incomplete(tmp_path: Path) -> None:
    fn = _resolve("run_m2_ladder")
    path = tmp_path / "partial_alpha.json"
    try:
        save = importlib.import_module(
            "blueberries_voi.sim.alpha_tune"
        ).save_tuned_alpha_table
        save(path, {"sw": 0.9})  # missing other CTL-05 arms
    except (ImportError, AttributeError):
        path.write_text('{"sw": 0.9}\n', encoding="utf-8")
    with pytest.raises(
        (FileNotFoundError, ValueError, RuntimeError, AssertionError, KeyError)
    ):
        fn(alpha_table_path=path, root_seed=1)


def test_ladder_profit_claim_path_invokes_t029_tuned_alpha_gate() -> None:
    """Harness must call require/assert tuned-alpha (T-029) - not invent a bypass."""
    mod = _resolve_ladder_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(mod.__file__))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
    required = {
        "require_tuned_alpha_table",
        "assert_ladder_profit_claim_allowed",
    }
    assert names & required, (
        "run_m2_ladder must wire T-029 require_tuned_alpha_table / "
        "assert_ladder_profit_claim_allowed before profit claims"
    )


# ---------------------------------------------------------------------------
# AC: numeric results under experiments/ and/or figures/m2/ - not controller/
# ---------------------------------------------------------------------------


def test_ladder_default_artifact_path_under_experiments_or_figures_m2() -> None:
    path_attr = None
    mod = _resolve_ladder_module()
    for name in (
        "DEFAULT_LADDER_RESULT_PATH",
        "DEFAULT_M2_LADDER_PATH",
        "DEFAULT_LADDER_ARTIFACT_PATH",
    ):
        if getattr(mod, name, None) is not None:
            path_attr = name
            break
    assert path_attr is not None, (
        "ladder module must document DEFAULT_* path under experiments/ or figures/m2/"
    )
    parts = Path(str(getattr(mod, path_attr))).as_posix()
    assert parts.startswith("experiments/") or parts.startswith("figures/m2/"), (
        f"{path_attr} must live under experiments/ or figures/m2/, got {parts!r}"
    )


def test_run_m2_ladder_writes_artifacts_outside_controller(tmp_path: Path) -> None:
    fn = _resolve("run_m2_ladder")
    alpha_path = _write_minimal_alpha_table(tmp_path / "tuned_alpha.json")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()

    kwargs: dict[str, Any] = {
        "alpha_table_path": alpha_path,
        "root_seed": 3,
    }
    sig = inspect.signature(fn).parameters
    if "out_dir" in sig:
        kwargs["out_dir"] = out_dir
    elif "artifact_dir" in sig:
        kwargs["artifact_dir"] = out_dir
    elif "output_dir" in sig:
        kwargs["output_dir"] = out_dir

    result = fn(**kwargs)
    written = getattr(result, "artifact_paths", None)
    if written is None:
        written = getattr(result, "written_paths", None)
    if written is None and isinstance(result, Mapping):
        written = result.get("artifact_paths", result.get("written_paths"))

    # Prefer explicit path list; else scan out_dir for new numeric artifacts.
    paths: list[Path]
    if written is not None:
        if isinstance(written, (str, Path)):
            paths = [Path(written)]
        elif isinstance(written, Sequence):
            paths = [Path(p) for p in written]
        else:
            paths = [Path(p) for p in written]
    else:
        paths = sorted(out_dir.rglob("*"))
        paths = [p for p in paths if p.is_file()]
        assert paths, (
            "run_m2_ladder must write numeric results under experiments/ "
            "and/or figures/m2/ (expose artifact_paths or accept out_dir)"
        )

    for path in paths:
        posix = path.as_posix()
        assert "/controller/" not in posix, (
            f"ladder artifact must not live under controller/: {posix}"
        )
        # Allow tmp_path experiments/ during tests; production defaults locked above.
        assert (
            "experiments" in path.parts
            or "figures" in path.parts
            or path.is_relative_to(tmp_path)
        ), f"unexpected artifact location: {posix}"


def test_ladder_runner_does_not_live_in_controller() -> None:
    """Figures / experiment writers stay outside controller/ (M2 agent brief)."""
    for path in _CONTROLLER_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "def run_m2_ladder" not in text, (
            f"run_m2_ladder must not be defined under controller/ ({path.name})"
        )


def test_controller_package_has_no_matplotlib_or_parquet_after_ladder() -> None:
    assert _CONTROLLER_DIR.is_dir()
    for path in sorted(_CONTROLLER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".", maxsplit=1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", maxsplit=1)[0])
        bad = imported & _FORBIDDEN_CONTROLLER_IMPORTS
        assert not bad, f"{path.name} imports forbidden roots: {sorted(bad)}"


# ---------------------------------------------------------------------------
# AC: production backend remains mean_field in ladder config
# ---------------------------------------------------------------------------


def test_ladder_config_production_backend_is_mean_field(tmp_path: Path) -> None:
    fn = _resolve("run_m2_ladder")
    mod = _resolve_ladder_module()
    alpha_path = _write_minimal_alpha_table(tmp_path / "tuned_alpha.json")
    result = fn(alpha_table_path=alpha_path, root_seed=11)

    backend = getattr(result, "production_backend", None)
    if backend is None:
        backend = getattr(result, "age_backend", None)
    if backend is None:
        backend = getattr(mod, "LADDER_PRODUCTION_BACKEND", None)
    if backend is None and isinstance(result, Mapping):
        backend = result.get("production_backend", result.get("age_backend"))
    assert backend == "mean_field", (
        "ladder config must keep production age backend mean_field "
        f"(T-021 / ADR 0091); got {backend!r}"
    )


def test_ladder_module_source_does_not_silently_select_joint() -> None:
    mod = _resolve_ladder_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8").lower()
    # Allow documenting joint as forbidden; reject wiring it as the default.
    if "production_backend" in source or "age_backend" in source:
        assert "mean_field" in source
    assert 'production_backend="joint"' not in source
    assert "production_backend='joint'" not in source


# ---------------------------------------------------------------------------
# AC: no new runtime dependencies
# ---------------------------------------------------------------------------


def test_no_new_runtime_dependencies_for_t032() -> None:
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _LOCKED_RUNTIME_DEPS, (
        f"runtime dependencies changed for T-032: {sorted(names)} "
        f"(locked {sorted(_LOCKED_RUNTIME_DEPS)})"
    )
