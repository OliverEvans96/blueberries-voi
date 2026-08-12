"""T-033 multi-scenario closed-loop + L remeasure — expected RED until runner lands.

Locks M2 eval scenarios: closed-loop under **P1** vs **B-state** vs **Rung 0**,
empirical L under SW+rollout recorded in MD outside ``controller/``, production
``mean_field`` (no silent joint revert), other masks interface-smoke only, and
``day_step`` + ``ShelfBelief`` factories on the primary path.
See ``.team/specs/T-033.md``.
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
_EXPERIMENTS = _REPO_ROOT / "experiments"
_TEAM_REPORTS = _REPO_ROOT / ".team" / "reports"

_MULTI_MODULE_CANDIDATES: tuple[str, ...] = (
    "blueberries_voi.sim.m2_multi_scenario",
    "blueberries_voi.viz.m2_multi_scenario",
    "blueberries_voi.experiments.m2_multi_scenario",
)

_PRIMARY_SCENARIOS: tuple[str, ...] = ("P1", "B-state", "Rung 0")
# Canonical aliases implement may use in result maps / MD headings.
_PRIMARY_ALIASES: dict[str, frozenset[str]] = {
    "P1": frozenset({"p1", "scn-p1", "scn_p1"}),
    "B-state": frozenset({"b-state", "b_state", "bstate", "scn-b-state", "oracle"}),
    "Rung 0": frozenset({"rung 0", "rung0", "rung_0", "age-blind", "age_blind"}),
}

_OTHER_MASKS: tuple[str, ...] = ("P0", "F1", "F1s", "F2a", "F2")

_FORBIDDEN_CONTROLLER_IMPORTS = frozenset({"matplotlib", "pyplot", "pyarrow"})
_LOCKED_RUNTIME_DEPS = frozenset({"matplotlib", "numpy", "pyarrow", "scipy"})

_MEAN_FIELD_RE = re.compile(r"mean[_\s-]?field", re.IGNORECASE)
_EMPIRICAL_L_RE = re.compile(
    r"(empirical\s*l|remeasured?\s*l|live[_\s-]?cohort\s*l|\bL\b.{0,40}"
    r"(p50|p90|max|median))",
    re.IGNORECASE | re.DOTALL,
)
_SW_ROLLOUT_RE = re.compile(
    r"(sw\s*\+\s*rollout|sw\+rollout|survival[_\s-]?weighted.{0,40}rollout|"
    r"rollout.{0,40}(sw|survival)|controller\s+config)",
    re.IGNORECASE | re.DOTALL,
)
_NO_JOINT_REVERT_RE = re.compile(
    r"(no\s+silent\s+.*joint|not\s+.*revert.*joint|remain(?:s|ing)?\s+"
    r"mean[_\s-]?field|does\s+not\s+recommend.{0,40}joint)",
    re.IGNORECASE | re.DOTALL,
)


def _resolve_multi_module() -> Any:
    errors: list[str] = []
    for name in _MULTI_MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            errors.append(f"{name}: {exc}")
    pytest.fail(
        "T-033 requires run_m2_multi_scenario module "
        f"(tried {list(_MULTI_MODULE_CANDIDATES)}): {'; '.join(errors)}",
        pytrace=False,
    )


def _resolve(attr: str) -> Any:
    mod = _resolve_multi_module()
    found = getattr(mod, attr, None)
    if found is not None:
        return found
    try:
        sim = importlib.import_module("blueberries_voi.sim")
    except ImportError:
        sim = None
    if sim is not None:
        found = getattr(sim, attr, None)
        if found is not None:
            return found
    pytest.fail(
        f"{attr} must be exported from {_MULTI_MODULE_CANDIDATES[0]} "
        "(see .team/specs/T-033.md Interfaces)",
        pytrace=False,
    )


def _norm_label(label: str) -> str:
    return re.sub(r"[\s_]+", " ", label.strip().lower())


def _matches_primary(label: str, primary: str) -> bool:
    n = _norm_label(label)
    if n == _norm_label(primary):
        return True
    return n in _PRIMARY_ALIASES[primary]


def _result_scenario_labels(result: Any) -> set[str]:
    labels: set[str] = set()
    for attr in ("scenarios", "primary_scenarios", "points", "arms", "beliefs"):
        raw = getattr(result, attr, None)
        if raw is None and isinstance(result, Mapping):
            raw = result.get(attr)
        if raw is None:
            continue
        if isinstance(raw, Mapping):
            labels.update(str(k) for k in raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            labels.update(str(x) for x in raw)
    for attr in ("profits", "metrics", "results", "by_scenario"):
        raw = getattr(result, attr, None)
        if raw is None and isinstance(result, Mapping):
            raw = result.get(attr)
        if isinstance(raw, Mapping):
            labels.update(str(k) for k in raw)
    return labels


def _artifact_paths_from_result(result: Any, out_dir: Path | None) -> list[Path]:
    written = getattr(result, "artifact_paths", None)
    if written is None:
        written = getattr(result, "written_paths", None)
    if written is None and isinstance(result, Mapping):
        written = result.get("artifact_paths", result.get("written_paths"))
    if written is None:
        report = getattr(result, "report_path", None)
        if report is None and isinstance(result, Mapping):
            report = result.get("report_path")
        if report is not None:
            written = report
    paths: list[Path]
    if written is not None:
        if isinstance(written, (str, Path)):
            paths = [Path(written)]
        elif isinstance(written, Sequence):
            paths = [Path(p) for p in written]
        else:
            paths = [Path(p) for p in written]
    elif out_dir is not None:
        paths = [p for p in sorted(out_dir.rglob("*")) if p.is_file()]
    else:
        paths = []
    return paths


def _invoke_runner(fn: Any, *, root_seed: int, out_dir: Path | None = None) -> Any:
    kwargs: dict[str, Any] = {"root_seed": root_seed}
    sig = inspect.signature(fn).parameters
    if out_dir is not None:
        if "out_dir" in sig:
            kwargs["out_dir"] = out_dir
        elif "artifact_dir" in sig:
            kwargs["artifact_dir"] = out_dir
        elif "output_dir" in sig:
            kwargs["output_dir"] = out_dir
        elif "report_dir" in sig:
            kwargs["report_dir"] = out_dir
    # Keep CI smoke short when the runner exposes burn/score knobs.
    for name, value in (
        ("n_burn", 1),
        ("n_score", 2),
        ("n_rollout_paths", 1),
        ("H", 2),
    ):
        if name in sig:
            kwargs[name] = value
    return fn(**kwargs)


def _read_md_candidates(paths: Sequence[Path]) -> str:
    texts: list[str] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            texts.append(path.read_text(encoding="utf-8"))
    return "\n".join(texts)


def _find_published_md_on_disk() -> list[Path]:
    """Locate T-033 multi-scenario / L-remeasure MD under allowed roots."""
    roots = (_EXPERIMENTS, _REPO_ROOT / "figures" / "m2", _TEAM_REPORTS)
    patterns = (
        "*multi*scenario*",
        "*m2*scenario*",
        "*l*remeasure*",
        "*empirical*l*",
        "*m2*l*",
    )
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pat in patterns:
            found.extend(
                p
                for p in root.glob(pat)
                if p.is_file() and p.suffix.lower() in {".md", ".txt"}
            )
            found.extend(
                p
                for p in root.rglob(pat)
                if p.is_file() and p.suffix.lower() in {".md", ".txt"}
            )
    # De-dupe while preserving order.
    seen: set[Path] = set()
    uniq: list[Path] = []
    for path in found:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        uniq.append(path)
    return uniq


# ---------------------------------------------------------------------------
# AC: run_m2_multi_scenario(*, root_seed, ...) -> MultiScenarioResult
# ---------------------------------------------------------------------------


def test_run_m2_multi_scenario_is_exportable() -> None:
    fn = _resolve("run_m2_multi_scenario")
    assert callable(fn)


def test_multi_scenario_result_type_is_exportable() -> None:
    result_type = _resolve("MultiScenarioResult")
    assert result_type is not None


def test_run_m2_multi_scenario_signature_requires_root_seed() -> None:
    fn = _resolve("run_m2_multi_scenario")
    params = inspect.signature(fn).parameters
    assert "root_seed" in params
    assert params["root_seed"].kind is inspect.Parameter.KEYWORD_ONLY


def test_run_m2_multi_scenario_smoke_compares_p1_bstate_rung0(
    tmp_path: Path,
) -> None:
    """Primary closed-loop scenarios: P1 vs B-state vs Rung 0."""
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=33, out_dir=out_dir)

    labels = _result_scenario_labels(result)
    assert labels, (
        "MultiScenarioResult must expose primary scenario labels "
        "(scenarios / profits / by_scenario / …)"
    )
    for primary in _PRIMARY_SCENARIOS:
        assert any(_matches_primary(lab, primary) for lab in labels), (
            f"primary scenario {primary!r} missing from result labels {sorted(labels)}"
        )


def test_run_m2_multi_scenario_publishes_md_comparing_primary_scenarios(
    tmp_path: Path,
) -> None:
    """Closed-loop runs publish a short MD comparing P1 vs B-state vs Rung 0."""
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=7, out_dir=out_dir)

    paths = _artifact_paths_from_result(result, out_dir)
    md_paths = [p for p in paths if p.suffix.lower() in {".md", ".txt"}]
    assert md_paths, (
        "run_m2_multi_scenario must write a short MD report "
        "(expose artifact_paths / report_path or write under out_dir)"
    )
    body = _read_md_candidates(md_paths)
    lower = body.lower()
    for primary in _PRIMARY_SCENARIOS:
        aliases = {_norm_label(primary), *_PRIMARY_ALIASES[primary]}
        assert any(a in lower for a in aliases), (
            f"MD report must mention primary scenario {primary!r}; "
            f"files={[p.name for p in md_paths]}"
        )


# ---------------------------------------------------------------------------
# AC: report under experiments/ and/or figures/m2/ (not controller/);
#     empirical L may also land under .team/reports/
# ---------------------------------------------------------------------------


def test_multi_scenario_default_artifact_path_outside_controller() -> None:
    mod = _resolve_multi_module()
    path_attr = None
    for name in (
        "DEFAULT_MULTI_SCENARIO_REPORT_PATH",
        "DEFAULT_REPORT_PATH",
        "DEFAULT_MULTI_SCENARIO_RESULT_PATH",
        "DEFAULT_RESULT_PATH",
    ):
        if hasattr(mod, name):
            path_attr = name
            break
    assert path_attr is not None, (
        "multi-scenario module must document DEFAULT_* path under experiments/ "
        "or figures/m2/ (L notes may use .team/reports/)"
    )
    parts = Path(str(getattr(mod, path_attr))).as_posix()
    allowed = (
        parts.startswith("experiments/")
        or parts.startswith("figures/m2/")
        or parts.startswith(".team/reports/")
    )
    assert allowed, (
        f"{path_attr} must live under experiments/, figures/m2/, or "
        f".team/reports/, got {parts!r}"
    )
    assert "/controller/" not in parts


def test_run_m2_multi_scenario_writes_artifacts_outside_controller(
    tmp_path: Path,
) -> None:
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=3, out_dir=out_dir)
    paths = _artifact_paths_from_result(result, out_dir)
    assert paths, (
        "run_m2_multi_scenario must write MD/numeric artifacts under "
        "experiments/ and/or figures/m2/ (never controller/)"
    )
    for path in paths:
        posix = path.as_posix()
        assert "/controller/" not in posix, (
            f"multi-scenario artifact must not live under controller/: {posix}"
        )
        assert (
            "experiments" in path.parts
            or "figures" in path.parts
            or "reports" in path.parts
            or path.is_relative_to(tmp_path)
        ), f"unexpected artifact location: {posix}"


def test_multi_scenario_runner_does_not_live_in_controller() -> None:
    for path in _CONTROLLER_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "def run_m2_multi_scenario" not in text, (
            f"run_m2_multi_scenario must not be defined under controller/ ({path.name})"
        )


def test_controller_package_has_no_matplotlib_or_parquet_after_multi_scenario() -> None:
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
# AC: empirical L under SW+rollout recorded in MD
# ---------------------------------------------------------------------------


def test_empirical_l_under_sw_rollout_recorded_in_md(tmp_path: Path) -> None:
    """FIL-13 follow-up: remeasure empirical L under SW+rollout / documented CTL."""
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=19, out_dir=out_dir)

    paths = _artifact_paths_from_result(result, out_dir)
    md_body = _read_md_candidates(paths)
    # Also accept a checked-in note under experiments/ or .team/reports/.
    disk_mds = _find_published_md_on_disk()
    if disk_mds:
        md_body = md_body + "\n" + _read_md_candidates(disk_mds)

    assert md_body.strip(), (
        "expected MD under experiments/, figures/m2/, or .team/reports/ "
        "recording empirical L (runner artifact_paths or published note)"
    )
    assert _EMPIRICAL_L_RE.search(md_body), (
        "report must record empirical L (p50/p90/max or explicit 'empirical L')"
    )
    assert _SW_ROLLOUT_RE.search(md_body), (
        "L remeasure must cite SW+rollout (or documented controller config)"
    )

    # Prefer a numeric L value somewhere in the note.
    has_numeric_l = bool(
        re.search(
            r"(?:\bL\b|empirical).{0,80}?\b\d+(?:\.\d+)?\b"
            r"|\b(?:p50|p90|max|median)\s*[=:]?\s*\d+",
            md_body,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )
    assert has_numeric_l, "empirical L note must include at least one numeric L value"


# ---------------------------------------------------------------------------
# AC: production remains mean_field; no silent joint revert
# ---------------------------------------------------------------------------


def test_multi_scenario_config_production_backend_is_mean_field(
    tmp_path: Path,
) -> None:
    fn = _resolve("run_m2_multi_scenario")
    mod = _resolve_multi_module()
    result = _invoke_runner(fn, root_seed=11, out_dir=tmp_path / "experiments")

    backend = getattr(result, "production_backend", None)
    if backend is None:
        backend = getattr(result, "age_backend", None)
    if backend is None:
        backend = getattr(mod, "MULTI_SCENARIO_PRODUCTION_BACKEND", None)
    if backend is None:
        backend = getattr(mod, "PRODUCTION_BACKEND", None)
    if backend is None and isinstance(result, Mapping):
        backend = result.get("production_backend", result.get("age_backend"))
    assert backend == "mean_field", (
        "multi-scenario config must keep production age backend mean_field "
        f"(T-021 / ADR 0091); got {backend!r}"
    )

    from blueberries_voi.filter import PRODUCTION_BACKEND

    assert PRODUCTION_BACKEND == "mean_field"


def test_multi_scenario_module_source_does_not_silently_select_joint() -> None:
    mod = _resolve_multi_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8").lower()
    if "production_backend" in source or "age_backend" in source:
        assert "mean_field" in source
    assert 'production_backend="joint"' not in source
    assert "production_backend='joint'" not in source
    assert 'production_backend="full_joint"' not in source
    assert "production_backend='full_joint'" not in source


def test_published_md_states_mean_field_and_rejects_silent_joint_revert(
    tmp_path: Path,
) -> None:
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=23, out_dir=out_dir)
    paths = _artifact_paths_from_result(result, out_dir)
    body = _read_md_candidates(paths)
    disk = _find_published_md_on_disk()
    if disk:
        body = body + "\n" + _read_md_candidates(disk)
    assert body.strip(), "multi-scenario / L MD must exist to lock mean_field wording"
    assert _MEAN_FIELD_RE.search(body), (
        "report must explicitly state production age backend remains mean_field"
    )
    assert _NO_JOINT_REVERT_RE.search(body), (
        "report must not recommend a silent revert to joint "
        "(state mean_field remains / no silent joint)"
    )


# ---------------------------------------------------------------------------
# AC: other masks interface smoke only (no full profit claims required)
# ---------------------------------------------------------------------------


def test_other_masks_have_interface_smoke_only(tmp_path: Path) -> None:
    """P0/F1/F1s/F2a/F2: callable smoke; no full profit-claim requirement."""
    fn = _resolve("run_m2_multi_scenario")
    mod = _resolve_multi_module()

    smoke = getattr(mod, "smoke_other_masks", None)
    if smoke is None:
        smoke = getattr(mod, "smoke_mask_interfaces", None)
    if smoke is None:
        smoke = getattr(mod, "interface_smoke_other_masks", None)

    if callable(smoke):
        out = smoke()
        if isinstance(out, Mapping):
            keys = {str(k) for k in out}
        elif isinstance(out, Sequence) and not isinstance(out, (str, bytes)):
            keys = {str(x) for x in out}
        else:
            keys = set()
        for mask in _OTHER_MASKS:
            assert any(_norm_label(mask) == _norm_label(k) for k in keys) or out, (
                f"other-mask smoke must cover {mask!r}; got {out!r}"
            )
        return

    # Fallback: runner accepts other_masks= / include_other_masks= and marks smoke.
    sig = inspect.signature(fn).parameters
    kwargs: dict[str, Any] = {"root_seed": 41}
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    if "out_dir" in sig:
        kwargs["out_dir"] = out_dir
    elif "artifact_dir" in sig:
        kwargs["artifact_dir"] = out_dir
    if "other_masks" in sig:
        kwargs["other_masks"] = list(_OTHER_MASKS)
    elif "include_other_masks" in sig:
        kwargs["include_other_masks"] = True
    elif "smoke_masks" in sig:
        kwargs["smoke_masks"] = list(_OTHER_MASKS)
    else:
        pytest.fail(
            "T-033 must expose smoke_other_masks(...) or run_m2_multi_scenario "
            "kwargs other_masks=/include_other_masks=/smoke_masks= for "
            f"{list(_OTHER_MASKS)} (interface smoke only)",
            pytrace=False,
        )

    for name, value in (("n_burn", 1), ("n_score", 1)):
        if name in sig:
            kwargs[name] = value
    result = fn(**kwargs)
    smoke_field = getattr(result, "other_mask_smoke", None)
    if smoke_field is None:
        smoke_field = getattr(result, "mask_smoke", None)
    if smoke_field is None and isinstance(result, Mapping):
        smoke_field = result.get("other_mask_smoke", result.get("mask_smoke"))
    assert smoke_field is not None, (
        "when using runner kwargs, MultiScenarioResult must record "
        "other_mask_smoke / mask_smoke (interface only — not full profit claims)"
    )


# ---------------------------------------------------------------------------
# AC: primary physics day_step; belief path ShelfBelief factories
# ---------------------------------------------------------------------------


def test_multi_scenario_forward_path_uses_shared_day_step() -> None:
    mod = _resolve_multi_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(mod.__file__))

    imports_day_step = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = {alias.name for alias in node.names}
            if "day_step" in names and (
                node.module == "blueberries_voi.model"
                or node.module.endswith(".model")
                or "sim" in node.module
            ):
                imports_day_step = True
        if isinstance(node, ast.Attribute) and node.attr == "day_step":
            imports_day_step = True
        if isinstance(node, ast.Name) and node.id == "day_step":
            imports_day_step = True
    assert imports_day_step or "day_step" in source, (
        f"{Path(mod.__file__).name} must use shared model.day_step "
        "(via run_closed_loop_episode / direct import)"
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "day_step":
            pytest.fail(
                "multi-scenario runner must not define a local day_step shadow",
                pytrace=False,
            )


def test_multi_scenario_belief_path_uses_shelf_belief_factories() -> None:
    mod = _resolve_multi_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "ShelfBelief" in source or "shelf_belief_from_" in source, (
        "belief path must use ShelfBelief factories "
        "(shelf_belief_from_rbpf / shelf_belief_from_oracle)"
    )
    # P1 → RBPF factory; B-state → oracle factory (Rung 0 may be policy-side).
    has_rbpf = "shelf_belief_from_rbpf" in source
    has_oracle = "shelf_belief_from_oracle" in source
    assert has_rbpf and has_oracle, (
        "multi-scenario module must reference shelf_belief_from_rbpf (P1) and "
        "shelf_belief_from_oracle (B-state); "
        f"rbpf={has_rbpf}, oracle={has_oracle}"
    )


def test_rung0_arm_orders_positive_on_empty_shelf() -> None:
    """Rung 0 must wire NB protection-interval demand_target (not default 0)."""
    from blueberries_voi.controller.damped_sw import PROTECTION_DEMAND_DAYS
    from blueberries_voi.controller.rung0 import CorrectedAgeBlindPolicy
    from blueberries_voi.filter.belief import ShelfBelief
    from blueberries_voi.model import ModelParams
    from scipy.stats import nbinom

    mod = _resolve_multi_module()
    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "demand_target" in source, (
        "CorrectedAgeBlindPolicy must be built with demand_target "
        "(protection-interval NB fractile); default 0 never orders"
    )

    params = ModelParams()
    alpha = 0.9
    d_star = float(
        nbinom.ppf(
            alpha,
            float(params.nb_r()) * float(PROTECTION_DEMAND_DAYS),
            float(params.nb_p()),
        )
    )
    assert d_star > 0.0
    # Mirror run_m2_multi_scenario Rung 0 construction.
    fractile_fn = getattr(mod, "_protection_demand_fractile", None)
    if callable(fractile_fn):
        wired = float(fractile_fn(alpha, params))
        assert wired == pytest.approx(d_star)

    policy = CorrectedAgeBlindPolicy(
        alpha=alpha,
        params=params,
        demand_target=d_star,
        protection_days=PROTECTION_DEMAND_DAYS,
        case_size=int(params.case_size),
    )
    empty = ShelfBelief(lot_counts=[], age_marginals=[], tau_grid=[0.0, 2.0, 4.0])
    qty = int(policy.order(0, empty, pending_orders={}))
    assert qty > 0, (
        f"Rung 0 on empty shelf / zero pending must order > 0 "
        f"(demand_target={d_star}); got {qty}"
    )


# ---------------------------------------------------------------------------
# AC: non-plot core smoke; no new runtime deps
# ---------------------------------------------------------------------------


def test_run_m2_multi_scenario_non_plot_core_smoke(tmp_path: Path) -> None:
    """Non-plot core smoke; full MD may stay experiment-only."""
    fn = _resolve("run_m2_multi_scenario")
    out_dir = tmp_path / "experiments"
    out_dir.mkdir()
    result = _invoke_runner(fn, root_seed=5, out_dir=out_dir)
    assert result is not None
    # Non-plot core: result object + at least one primary label / backend field.
    labels = _result_scenario_labels(result)
    backend = getattr(result, "production_backend", None)
    if backend is None and isinstance(result, Mapping):
        backend = result.get("production_backend")
    assert labels or backend == "mean_field" or hasattr(result, "artifact_paths"), (
        "non-plot core must return a MultiScenarioResult with scenarios, "
        "production_backend, or artifact_paths"
    )


def test_no_new_runtime_dependencies_for_t033() -> None:
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw = data["project"]["dependencies"]
    names: set[str] = set()
    for spec in raw:
        name = re.split(r"[<>=!\[]", spec, maxsplit=1)[0].strip().lower()
        names.add(name)
    assert names == _LOCKED_RUNTIME_DEPS, (
        f"runtime dependencies changed for T-033: {sorted(names)} "
        f"(locked {sorted(_LOCKED_RUNTIME_DEPS)})"
    )
