"""T-068 / ADR 0105: unique-MF dedup retired from production ``_pf_update``.

T-064 required unique-particle ``mean_field_update`` dedup on the production path.
ADR 0105 removes production MF; these guards encode the supersession.
Diagnostic ``mean_field_update`` API tests remain in ``test_age_likelihood.py``.
"""

from __future__ import annotations

import pytest

pytest.skip("T-121 F3: production particle filter removed", allow_module_level=True)

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from blueberries_voi.filter.particle.research import ResearchParticleFilter

from blueberries_voi.filter.types import UNOBSERVED, RichObs, mask_for
from blueberries_voi.model import ModelParams

_RUNTIME_DEPS_LOCKED = frozenset({"numpy", "scipy"})


def _backends_source() -> str:
    import blueberries_voi.filter.backends as backends

    return Path(backends.__file__).read_text(encoding="utf-8")


def _ast_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    msg = f"function {name!r} not found in source"
    raise AssertionError(msg)


def _names_in_function(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _p1_unobserved_maps(
    *,
    sales_total: int = 4,
    waste_total: int = 1,
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


def test_adr_0105_accepted_supersedes_production_mf_hot_path() -> None:
    root = Path(__file__).resolve().parents[1]
    adr = root / ".team/adr/0105-arrival-only-age-counts-only-exact-wor.md"
    text = adr.read_text(encoding="utf-8")
    assert "STATUS: ACCEPTED" in text
    assert "0103" in text or "mean_field_update" in text


def test_no_new_runtime_deps() -> None:
    import tomllib

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    names = {
        d.split(">=")[0].split("==")[0].split("[")[0].strip().lower() for d in deps
    }
    assert names <= _RUNTIME_DEPS_LOCKED


def test_particle_filter_update_does_not_name_mean_field_update() -> None:
    fn = _ast_function(_backends_source(), "_particle_filter_update")
    assert "mean_field_update" not in _names_in_function(fn)


def test_duplicate_particles_do_not_invoke_mean_field_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production path: MF must not run even when particles share fingerprints."""
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

    n_particles, k, n_lots = 6, 4, 2
    particle_filter = ResearchParticleFilter(
        params=ModelParams(), N=n_particles, K=k, L=n_lots
    )
    rng = np.random.default_rng(42)
    particle_filter.initialize(rng)
    assert particle_filter._state is not None

    counts_a = np.asarray([5, 5], dtype=int)
    counts_b = np.asarray([4, 6], dtype=int)
    post_a = np.ones((n_lots, k), dtype=float) / k
    post_b = np.asarray([[0.7, 0.1, 0.1, 0.1], [0.1, 0.7, 0.1, 0.1]], dtype=float)
    particle_filter._state.counts[:] = np.vstack(
        [counts_a, counts_a, counts_a, counts_b, counts_b, counts_a]
    )
    particle_filter._state.age_post[:] = np.stack(
        [post_a, post_a, post_a, post_b, post_b, post_a], axis=0
    )

    particle_filter.step(
        _p1_unobserved_maps(sales_total=4, waste_total=1, arrivals=0), rng
    )
    assert not calls, (
        "unique-MF dedup is retired: production _particle_filter_update must not call "
        "mean_field_update (ADR 0105)"
    )


def test_mean_field_update_still_importable_off_production_path() -> None:
    from blueberries_voi.filter.age_likelihood import mean_field_update

    assert callable(mean_field_update)
