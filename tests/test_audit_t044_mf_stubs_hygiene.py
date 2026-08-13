"""T-044: MF sweeps=5, bakeoff stub markers, backlog/docstring hygiene.

See `.team/specs/T-044.md` and ADR 0097.
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
_AGE_LIKELIHOOD = _REPO_ROOT / "src" / "blueberries_voi" / "filter" / "age_likelihood.py"
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
            return int(getattr(mod, "MF_MAX_SWEEPS"))
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
# AC: MF_MAX_SWEEPS = 5 shared; production P1 path uses it
# ---------------------------------------------------------------------------


def test_mf_max_sweeps_constant_is_five() -> None:
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


def test_backends_p1_path_no_hardcoded_max_sweeps_two() -> None:
    """Production P1 path must not hard-code max_sweeps=2."""
    source = _BACKENDS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_rbpf_update":
            fn = node
            break
    assert fn is not None, "_rbpf_update missing in backends.py"
    # Look for max_sweeps=2 literal in the function body.
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "max_sweeps" and isinstance(kw.value, ast.Constant):
                    assert kw.value.value != 2, (
                        "production _rbpf_update must not hard-code max_sweeps=2; "
                        "use MF_MAX_SWEEPS (5) unless caller overrides"
                    )


def test_production_p1_invokes_mean_field_with_max_sweeps_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import blueberries_voi.filter.age_likelihood as age_likelihood
    import blueberries_voi.filter.backends as backends

    sweeps_seen: list[int] = []
    real = age_likelihood.mean_field_update

    def _spy(*args: Any, **kwargs: Any) -> Any:
        if "max_sweeps" in kwargs:
            sweeps_seen.append(int(kwargs["max_sweeps"]))
        else:
            # Default parameter path — resolve from signature.
            default = inspect.signature(real).parameters["max_sweeps"].default
            sweeps_seen.append(int(default))
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
    assert sweeps_seen, "mean_field_update not invoked on P1 path"
    assert all(s == 5 for s in sweeps_seen), (
        f"production P1 mean_field_update must use max_sweeps=5 by default, "
        f"got {sweeps_seen}"
    )


# ---------------------------------------------------------------------------
# AC: bakeoff stubs marked; MeanFieldBackend is production
# ---------------------------------------------------------------------------


def test_sliding_window_backend_is_marked_non_citeable_stub() -> None:
    from blueberries_voi.filter.backends import SlidingWindowBackend

    cls = SlidingWindowBackend
    doc = (cls.__doc__ or "").lower()
    assert doc, "SlidingWindowBackend needs a class docstring"
    assert any(
        token in doc
        for token in ("stub", "non-production", "non-citeable", "not cite", "bakeoff")
    ), (
        "SlidingWindowBackend docstring must state non-production / non-citeable stub"
    )
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


def test_mean_field_backend_is_not_marked_stub() -> None:
    from blueberries_voi.filter.backends import MeanFieldBackend

    cls = MeanFieldBackend
    flag = _stub_flag(cls)
    # Convention: False, or attribute absent.
    assert flag is not True, (
        "MeanFieldBackend is production and must not be marked is_stub=True"
    )
    if flag is False:
        assert _stub_flag(cls()) is False


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