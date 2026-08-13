"""T-044: MF sweeps=5, bakeoff stub markers, backlog/docstring hygiene.

See `.team/specs/T-044-audit-remediation.md` and ADR 0104.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from blueberries_voi.filter import RBPF
from blueberries_voi.filter.types import UNOBSERVED, RichObs, mask_for
from blueberries_voi.model import ModelParams

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKENDS = _REPO_ROOT / "src" / "blueberries_voi" / "filter" / "backends.py"
_AGE_LIKELIHOOD = (
    _REPO_ROOT / "src" / "blueberries_voi" / "filter" / "age_likelihood.py"
)
_CONTROLLER_INIT = _REPO_ROOT / "src" / "blueberries_voi" / "controller" / "__init__.py"
_ALPHA_TUNE = _REPO_ROOT / "src" / "blueberries_voi" / "sim" / "alpha_tune.py"
_BACKLOG = _REPO_ROOT / ".team" / "backlog.md"


def _resolve_mf_max_sweeps() -> int:
    """Shared MF_MAX_SWEEPS constant (age_likelihood and/or backends)."""
    for mod_name in (
        "blueberries_voi.filter.age_likelihood",
        "blueberries_voi.filter.backends",
        "blueberries_voi.filter",
    ):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        if hasattr(mod, "MF_MAX_SWEEPS"):
            return int(mod.MF_MAX_SWEEPS)
    pytest.fail(
        "shared library constant MF_MAX_SWEEPS=5 must be exported "
        "(filter.age_likelihood and/or filter.backends) — T-044",
        pytrace=False,
    )


def _stub_flag(obj: Any) -> bool | None:
    for name in ("is_stub", "IS_STUB"):
        if hasattr(obj, name):
            return bool(getattr(obj, name))
    return None


def _p1_unobserved_maps(
    *,
    sales_total: int = 10,
    waste_total: int = 2,
    arrivals: int = 0,
) -> RichObs:
    return mask_for("P1").apply(
        RichObs(
            arrivals=arrivals,
            sales_total=sales_total,
            waste_total=waste_total,
            sales_by_lot={1: sales_total, 2: 0},
            waste_by_lot={1: waste_total, 2: 0},
            pack_date=UNOBSERVED,
            age_at_receipt=UNOBSERVED,
            lot_ids_live=UNOBSERVED,
        )
    )


# ---------------------------------------------------------------------------
# AC: MF_MAX_SWEEPS = 5 for diagnostic mean_field_update API (not production)
# ---------------------------------------------------------------------------


def test_mf_max_sweeps_constant_is_five() -> None:
    """Diagnostic MF API keeps MF_MAX_SWEEPS=5 (ADR 0104); not a production path."""
    assert _resolve_mf_max_sweeps() == 5


def test_age_likelihood_mean_field_default_uses_mf_max_sweeps() -> None:
    import blueberries_voi.filter.age_likelihood as al

    sweeps = _resolve_mf_max_sweeps()
    sig = inspect.signature(al.mean_field_update)
    assert "max_sweeps" in sig.parameters
    default = sig.parameters["max_sweeps"].default
    assert default == sweeps == 5, (
        f"mean_field_update max_sweeps default must be MF_MAX_SWEEPS=5, got {default}"
    )


def test_production_rbpf_update_does_not_call_mean_field_update() -> None:
    """ADR 0105 / T-068: retire production MF-sweep=5 requirements on _rbpf_update."""
    source = _BACKENDS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn: ast.FunctionDef | None = None
    for body_node in tree.body:
        if isinstance(body_node, ast.FunctionDef) and body_node.name == "_rbpf_update":
            fn = body_node
            break
    assert fn is not None, "_rbpf_update missing in backends.py"
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "mean_field_update" not in names, (
        "production _rbpf_update must not call mean_field_update (ADR 0105)"
    )


def test_production_p1_does_not_invoke_mean_field_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    calls: list[int] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(age_likelihood, "mean_field_update", _spy)
    if hasattr(backends, "mean_field_update"):
        monkeypatch.setattr(backends, "mean_field_update", _spy)

    rbpf = RBPF(params=ModelParams(), N=24, K=4, L=2)
    rng = np.random.default_rng(11)
    rbpf.initialize(rng)
    assert rbpf._state is not None
    rbpf._state.counts[:] = np.asarray([[6, 6]] * rbpf.N, dtype=int)
    obs = _p1_unobserved_maps(sales_total=8, waste_total=2)
    assert obs.sales_by_lot is UNOBSERVED
    rbpf.step(obs, rng)
    assert not calls, "production P1 path must not invoke mean_field_update (ADR 0105)"


# ---------------------------------------------------------------------------
# AC: bakeoff stubs marked; MeanFieldBackend is diagnostic / non-production age-MF
# ---------------------------------------------------------------------------


def test_sliding_window_backend_is_marked_non_citeable_stub() -> None:
    from blueberries_voi.filter.backends import SlidingWindowBackend

    cls = SlidingWindowBackend
    doc = (cls.__doc__ or "").lower()
    assert doc, "SlidingWindowBackend needs a class docstring"
    assert any(
        token in doc
        for token in ("stub", "non-production", "non-citeable", "not cite", "bakeoff")
    ), "SlidingWindowBackend docstring must state non-production / non-citeable stub"
    flag = _stub_flag(cls)
    assert flag is True, (
        "SlidingWindowBackend must expose machine-checkable is_stub/IS_STUB=True"
    )
    # Instance inherits the marker
    assert _stub_flag(cls()) is True


def test_full_joint_backend_is_marked_non_citeable_stub() -> None:
    from blueberries_voi.filter.backends import FullJointBackend

    cls = FullJointBackend
    doc = (cls.__doc__ or "").lower()
    assert doc, "FullJointBackend needs a class docstring"
    assert any(
        token in doc
        for token in ("stub", "non-production", "non-citeable", "not cite", "bakeoff")
    ), "FullJointBackend docstring must state non-production / non-citeable stub"
    flag = _stub_flag(cls)
    assert flag is True, (
        "FullJointBackend must expose machine-checkable is_stub/IS_STUB=True"
    )
    assert _stub_flag(cls()) is True


def test_mean_field_backend_may_be_marked_non_production() -> None:
    """ADR 0105: age-MF backend is no longer the production closed-loop identity."""
    from blueberries_voi.filter.backends import MeanFieldBackend

    cls = MeanFieldBackend
    doc = (cls.__doc__ or "").lower()
    flag = _stub_flag(cls)
    # Allowed: explicit stub/non-production marker, or docstring saying so.
    # Not required to remain unmarked production (supersedes T-044 production clause).
    if flag is True:
        return
    if any(
        token in doc
        for token in ("stub", "non-production", "non-citeable", "diagnostic", "bakeoff")
    ):
        return
    # Soft pass: class still importable for bakeoff/diagnostic use.
    assert cls is not None


# ---------------------------------------------------------------------------
# AC: controller docstring, alpha_tune comment, backlog hygiene
# ---------------------------------------------------------------------------


def test_controller_init_docstring_not_stubs_only() -> None:
    text = _CONTROLLER_INIT.read_text(encoding="utf-8")
    # Module docstring is the first string literal.
    tree = ast.parse(text)
    assert tree.body and isinstance(tree.body[0], ast.Expr)
    doc_node = tree.body[0].value
    assert isinstance(doc_node, ast.Constant) and isinstance(doc_node.value, str)
    doc = doc_node.value
    assert doc.strip() != "Controller stubs (M2).", (
        "controller/__init__.py must not say only 'Controller stubs (M2).'"
    )
    lower = doc.lower()
    assert any(
        tok in lower for tok in ("policy", "ordering", "controller", "rung", "rollout")
    ), "controller package docstring should describe the shipped controller surface"


def test_alpha_tune_comment_not_belief_none_stale() -> None:
    source = _ALPHA_TUNE.read_text(encoding="utf-8")
    stale = re.compile(
        r"closed-loop currently passes belief\s*=\s*None",
        re.IGNORECASE,
    )
    assert not stale.search(source), (
        "sim/alpha_tune.py must not claim closed-loop passes belief=None; "
        "correct or remove the stale comment (T-044)"
    )


def test_backlog_reflects_m2_m3_on_main() -> None:
    text = _BACKLOG.read_text(encoding="utf-8")
    lower = text.lower()
    # Stale: claims M2/M3 only tip-green pending merge onto main as if absent.
    stale = (
        "m2 complete pending human merge to main" in lower
        or "pending human merge with m2 tip to `main`" in lower
        or (
            "pending human merge" in lower
            and "m3" in lower
            and "do not reopen eng-01" in lower
        )
    )
    # Required: acknowledge library work landed on main (at/after f4a467f).
    on_main = (
        "f4a467f" in lower
        or re.search(
            r"m2\+?m3.{0,80}(library )?(work )?is on [`']?main[`']?",
            lower,
            re.DOTALL,
        )
        is not None
        or re.search(
            r"on [`']?main[`']?.{0,40}(at|after).{0,20}f4a467f",
            lower,
            re.DOTALL,
        )
        is not None
    )
    assert on_main and not stale, (
        ".team/backlog.md must reflect that M2+M3 library work is on main "
        "(at/after f4a467f), and must not claim M2/M3 are only tip-green "
        "pending merge as if absent (T-044)"
    )
