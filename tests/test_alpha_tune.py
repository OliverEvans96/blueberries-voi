"""T-029 CTL-03 α fractile tuning — expected RED until sim alpha-tune API lands.

Locks CTL-03=B simulation-tuned α per ladder arm under shared CRN, artifact I/O
under experiments/ and/or figures/m2/, SIM-01=B profit objective, controller
purity, and rejection of untuned ladder profit claims. See `.team/specs/T-029.md`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TUNE_MODULE = "blueberries_voi.sim.alpha_tune"
_CONTROLLER_DIR = _REPO_ROOT / "src" / "blueberries_voi" / "controller"

# Ladder arms that must have a tuned α entry (CTL-05). Rollout / DP may be
# placeholders until T-030 / T-031 land; the arm ids must still be registered.
_REQUIRED_ARMS: frozenset[str] = frozenset(
    {"constant", "rung0", "sw", "rollout", "dp"}
)
_AVAILABLE_NOW: frozenset[str] = frozenset({"constant", "rung0", "sw"})

# Tiny CI grid (open question: desktop defaults live in artifact header).
_CI_ALPHA_GRID: tuple[float, ...] = (0.7, 0.8, 0.9)

_FORBIDDEN_CONTROLLER_IMPORTS = frozenset({"matplotlib", "pyplot", "pyarrow"})


def _resolve(attr: str) -> Any:
    try:
        mod = importlib.import_module(_TUNE_MODULE)
    except ImportError as exc:
        pytest.fail(
            f"{_TUNE_MODULE} must exist for T-029 ({attr}): {exc}",
            pytrace=False,
        )
    found = getattr(mod, attr, None)
    assert found is not None, (
        f"{attr} must be exported from {_TUNE_MODULE} (see .team/specs/T-029.md)"
    )
    return found


def _tune_module() -> Any:
    try:
        return importlib.import_module(_TUNE_MODULE)
    except ImportError as exc:
        pytest.fail(f"{_TUNE_MODULE} must exist for T-029: {exc}", pytrace=False)


# ---------------------------------------------------------------------------
# AC: tune_alpha_grid entrypoint + per-arm surface
# ---------------------------------------------------------------------------


def test_tune_alpha_grid_exported_with_arm_alphas_root_seed() -> None:
    """Spec interface: tune_alpha_grid(arm_id, *, alphas, root_seed, ...) -> float."""
    fn = _resolve("tune_alpha_grid")
    assert callable(fn)
    sig = inspect.signature(fn)
    params = sig.parameters
    assert "arm_id" in params or next(iter(params)) is not None
    names = list(params)
    assert names[0] == "arm_id", "first positional arg must be arm_id"
    assert "alphas" in params
    assert params["alphas"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "root_seed" in params
    assert params["root_seed"].kind is inspect.Parameter.KEYWORD_ONLY


def test_ladder_alpha_arms_include_constant_rung0_sw_and_placeholders() -> None:
    arms = _resolve("LADDER_ALPHA_ARMS")
    arm_set = frozenset(arms)
    missing = _REQUIRED_ARMS - arm_set
    assert not missing, f"LADDER_ALPHA_ARMS missing {sorted(missing)}"


@pytest.mark.parametrize("arm_id", sorted(_AVAILABLE_NOW))
def test_tune_alpha_grid_returns_best_alpha_from_grid_per_arm(arm_id: str) -> None:
    """Per available ladder arm: grid search returns a candidate α under shared CRN."""
    tune = _resolve("tune_alpha_grid")
    best = tune(arm_id, alphas=_CI_ALPHA_GRID, root_seed=42)
    assert isinstance(best, float)
    assert best in _CI_ALPHA_GRID


def test_tune_alpha_grid_empty_alphas_rejected() -> None:
    tune = _resolve("tune_alpha_grid")
    with pytest.raises((ValueError, TypeError)):
        tune("rung0", alphas=(), root_seed=0)


def test_tune_alpha_grid_unknown_arm_rejected() -> None:
    tune = _resolve("tune_alpha_grid")
    with pytest.raises((ValueError, KeyError)):
        tune("not-an-arm", alphas=_CI_ALPHA_GRID, root_seed=0)


@pytest.mark.parametrize("arm_id", ["rollout", "dp"])
def test_placeholder_arms_registered_and_callable_or_documented(arm_id: str) -> None:
    """Rollout/DP placeholders must be listed; may raise until those tickets land."""
    arms = frozenset(_resolve("LADDER_ALPHA_ARMS"))
    assert arm_id in arms
    tune = _resolve("tune_alpha_grid")
    try:
        best = tune(arm_id, alphas=_CI_ALPHA_GRID, root_seed=7)
    except (NotImplementedError, ValueError) as exc:
        msg = str(exc).lower()
        assert "placeholder" in msg or arm_id in msg or "unavailable" in msg
        return
    assert isinstance(best, float)
    assert best in _CI_ALPHA_GRID


# ---------------------------------------------------------------------------
# AC: shared CRN across α candidates
# ---------------------------------------------------------------------------


def test_tune_alpha_grid_is_deterministic_under_shared_root_seed() -> None:
    """Same arm + alphas + root_seed → same best α (CRN / SIM-05 addressing)."""
    tune = _resolve("tune_alpha_grid")
    a = tune("sw", alphas=_CI_ALPHA_GRID, root_seed=99)
    b = tune("sw", alphas=_CI_ALPHA_GRID, root_seed=99)
    assert a == b


def test_tune_alpha_grid_evaluates_candidates_under_same_root_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """α candidates share one root_seed (paired CRN), not independent seeds per α."""
    mod = _tune_module()
    tune = _resolve("tune_alpha_grid")
    seen_seeds: list[int] = []

    # Prefer hooking a package helper if present; else wrap episode_profit path
    # used by the objective so we still observe shared addressing.
    if hasattr(mod, "evaluate_alpha_episode_profit"):
        real = mod.evaluate_alpha_episode_profit

        def _spy(*args: Any, **kwargs: Any) -> Any:
            if "root_seed" in kwargs:
                seen_seeds.append(int(kwargs["root_seed"]))
            elif len(args) >= 3:
                seen_seeds.append(int(args[2]))
            return real(*args, **kwargs)

        monkeypatch.setattr(mod, "evaluate_alpha_episode_profit", _spy)
    else:
        from blueberries_voi.sim import profit as profit_mod

        real_ep = profit_mod.episode_profit
        call_count = {"n": 0}

        def _count(*args: Any, **kwargs: Any) -> float:
            call_count["n"] += 1
            return float(real_ep(*args, **kwargs))

        monkeypatch.setattr(profit_mod, "episode_profit", _count)

        tune("rung0", alphas=_CI_ALPHA_GRID, root_seed=123)
        assert call_count["n"] >= len(_CI_ALPHA_GRID), (
            "objective must score each α candidate via episode_profit (SIM-01=B)"
        )
        return

    tune("rung0", alphas=_CI_ALPHA_GRID, root_seed=123)
    assert seen_seeds, "expected evaluate_alpha_episode_profit to be invoked"
    assert all(s == 123 for s in seen_seeds), (
        f"α candidates must share root_seed=123; saw {seen_seeds}"
    )
    assert len(seen_seeds) >= len(_CI_ALPHA_GRID)


# ---------------------------------------------------------------------------
# AC: tuned α artifact under experiments/ and/or figures/m2/
# ---------------------------------------------------------------------------


def test_default_tuned_alpha_artifact_path_under_experiments_or_figures_m2() -> None:
    path = Path(str(_resolve("DEFAULT_TUNED_ALPHA_PATH")))
    parts = path.as_posix()
    assert parts.startswith("experiments/") or parts.startswith("figures/m2/"), (
        f"DEFAULT_TUNED_ALPHA_PATH must live under experiments/ or figures/m2/, "
        f"got {parts!r}"
    )


def test_save_and_load_tuned_alpha_table_roundtrip(tmp_path: Path) -> None:
    save = _resolve("save_tuned_alpha_table")
    load = _resolve("load_tuned_alpha_table")
    table = {"constant": 0.8, "rung0": 0.7, "sw": 0.9, "rollout": 0.85, "dp": 0.75}
    out = tmp_path / "tuned_alpha.json"
    save(out, table)
    assert out.is_file()
    loaded = load(out)
    assert isinstance(loaded, Mapping)
    for arm, alpha in table.items():
        assert arm in loaded
        assert float(loaded[arm]) == pytest.approx(alpha)


def test_save_tuned_alpha_table_records_desktop_grid_header(tmp_path: Path) -> None:
    """Open question lock: desktop defaults documented in the artifact header."""
    save = _resolve("save_tuned_alpha_table")
    out = tmp_path / "tuned_alpha.md"
    save(
        out,
        {"rung0": 0.8, "sw": 0.85},
        header={"ci_alphas": list(_CI_ALPHA_GRID), "desktop_alphas": [0.5, 0.95]},
    )
    text = out.read_text(encoding="utf-8").lower()
    assert "desktop" in text or "0.5" in text
    assert "ci" in text or "0.7" in text


def test_artifact_path_documented_in_readme_or_module_docstring() -> None:
    mod = _tune_module()
    doc = (mod.__doc__ or "") + "\n"
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    figures_readme = _REPO_ROOT / "figures" / "m2" / "README.md"
    blob = doc + readme
    if figures_readme.is_file():
        blob += figures_readme.read_text(encoding="utf-8")
    path = str(_resolve("DEFAULT_TUNED_ALPHA_PATH"))
    assert path in blob or "tuned_alpha" in blob.lower(), (
        "artifact path must be documented in module docstring and/or README "
        f"(expected mention of {path!r} or tuned_alpha)"
    )


# ---------------------------------------------------------------------------
# AC: untuned path rejected for ladder profit claims
# ---------------------------------------------------------------------------


def test_require_tuned_alpha_table_fails_when_missing(tmp_path: Path) -> None:
    require = _resolve("require_tuned_alpha_table")
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        require(missing)


def test_ladder_profit_claim_rejected_without_tuned_alpha_table(
    tmp_path: Path,
) -> None:
    """Harness assertion: ladder profit claims must not proceed untuned."""
    claim = _resolve("assert_ladder_profit_claim_allowed")
    missing = tmp_path / "missing_tuned_alpha.json"
    with pytest.raises((FileNotFoundError, ValueError, RuntimeError, AssertionError)):
        claim(missing)


def test_ladder_profit_claim_allowed_when_tuned_table_present(tmp_path: Path) -> None:
    save = _resolve("save_tuned_alpha_table")
    claim = _resolve("assert_ladder_profit_claim_allowed")
    path = tmp_path / "tuned.json"
    save(
        path,
        {arm: 0.8 for arm in sorted(_REQUIRED_ARMS)},
    )
    # Must not raise when a complete tuned table is loaded.
    claim(path)


def test_ladder_profit_claim_rejected_for_incomplete_table(tmp_path: Path) -> None:
    save = _resolve("save_tuned_alpha_table")
    claim = _resolve("assert_ladder_profit_claim_allowed")
    path = tmp_path / "partial.json"
    save(path, {"sw": 0.9})  # missing other arms
    with pytest.raises((ValueError, RuntimeError, AssertionError, KeyError)):
        claim(path)


# ---------------------------------------------------------------------------
# AC: objective uses T-025 day/episode profit (SIM-01=B), not waste-only
# ---------------------------------------------------------------------------


def test_tune_module_uses_episode_profit_not_waste_only() -> None:
    mod = _tune_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(mod.__file__))
    imported: set[str] = set()
    names_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.Name):
            names_used.add(node.id)
        elif isinstance(node, ast.Attribute):
            names_used.add(node.attr)
    profit_symbols = {"episode_profit", "day_profit", "ProfitCosts"}
    assert profit_symbols & (imported | names_used), (
        "alpha tuning must use T-025 sim.profit (episode_profit / day_profit / "
        "ProfitCosts), not a waste-only objective"
    )
    # Waste-only smell: scoring only waste_total without sales/margin terms.
    if "waste_total" in names_used and "episode_profit" not in (
        imported | names_used
    ):
        pytest.fail(
            "tuning must not optimize waste_total alone; use episode_profit",
            pytrace=False,
        )


# ---------------------------------------------------------------------------
# AC: controller stays pure (no matplotlib); writers outside controller/
# ---------------------------------------------------------------------------


def test_controller_package_has_no_matplotlib() -> None:
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


def test_tune_alpha_grid_does_not_live_in_controller() -> None:
    """Tuning driver is sim/experiments helper — not a controller policy module."""
    ctrl = importlib.import_module("blueberries_voi.controller")
    assert not hasattr(ctrl, "tune_alpha_grid")
    for path in _CONTROLLER_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "def tune_alpha_grid" not in text, (
            f"tune_alpha_grid must not be defined under controller/ ({path.name})"
        )


def test_no_new_runtime_dependencies_for_t029() -> None:
    import tomllib

    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    locked = frozenset({"matplotlib", "numpy", "pyarrow", "scipy"})
    assert names == locked, (
        f"runtime dependencies changed for T-029: {sorted(names)} "
        f"(locked {sorted(locked)})"
    )
