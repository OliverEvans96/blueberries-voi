"""T-044 derived Abdella arrival-age product + browser-safe loaders (RED).

Locks ADR 0099 / ``.team/specs/T-044.md`` before production loaders exist:

* offline ``build_derived_abdella_product`` from vendored Parquet
* ``load_derived_abdella_arrival_ages`` without importing pyarrow
* injectable age arrays and product keys ``abdella_all`` / ``long_haul`` /
  ``short_haul`` (MOD-21 FL short-haul + CA→East long-haul mix)
* no EngineSession / ``simulator`` façade (T-043 stays out of scope)
"""

from __future__ import annotations

import ast
import importlib
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ABDELLA_PARQUET = _REPO_ROOT / "data" / "abdella"
_SRC = _REPO_ROOT / "src" / "blueberries_voi"

# Documented public surface (names may live under any candidate module).
_PRODUCT_MODULE_CANDIDATES = (
    "blueberries_voi.model.abdella_product",
    "blueberries_voi.model.derived_abdella",
    "blueberries_voi.model.arrival_ages",
    "blueberries_voi.data.abdella_product",
    "blueberries_voi.data.derived_abdella",
)

# Browser / interactive entry until ``simulator/`` exists (T-043). Prefer an
# explicit browser stub; fall back to the derived-product helper module.
_BROWSER_ENTRY_CANDIDATES = (
    "blueberries_voi.browser",
    "blueberries_voi.browser_entry",
    *_PRODUCT_MODULE_CANDIDATES,
)

_PRODUCT_KEYS = ("abdella_all", "long_haul", "short_haul")
_FORBIDDEN_BROWSER_IMPORT_ROOTS = frozenset({"matplotlib", "pyarrow", "pyarrow.parquet"})


def _resolve_product_module() -> Any:
    last_err: Exception | None = None
    for name in _PRODUCT_MODULE_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        "T-044 derived Abdella product module missing; tried "
        f"{_PRODUCT_MODULE_CANDIDATES}{detail}",
        pytrace=False,
    )


def _resolve_attr(*names: str) -> Any:
    mod = _resolve_product_module()
    for name in names:
        found = getattr(mod, name, None)
        if found is not None:
            return found
    pytest.fail(
        f"T-044 API missing; expected one of {names} on "
        f"{mod.__name__} per .team/specs/T-044.md",
        pytrace=False,
    )


def _resolve_browser_entry() -> Any:
    last_err: Exception | None = None
    for name in _BROWSER_ENTRY_CANDIDATES:
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            last_err = exc
            continue
    detail = f" ({last_err})" if last_err is not None else ""
    pytest.fail(
        "T-044 browser / interactive entry module missing; tried "
        f"{_BROWSER_ENTRY_CANDIDATES}{detail}",
        pytrace=False,
    )


def _ages_from_product(product: Any) -> np.ndarray:
    """Pull arrival-age array from ArrivalAgeProduct or array-like."""
    if isinstance(product, np.ndarray):
        return np.asarray(product, dtype=float)
    for attr in ("arrival_ages", "ages", "ages_d", "tau_in"):
        if hasattr(product, attr):
            return np.asarray(getattr(product, attr), dtype=float)
    if isinstance(product, (list, tuple)):
        return np.asarray(product, dtype=float)
    pytest.fail(
        "ArrivalAgeProduct must expose arrival-age array "
        "(arrival_ages / ages / ages_d / tau_in)",
        pytrace=False,
    )


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
            roots.add(node.module)
    return roots


@contextmanager
def _block_modules(*names: str) -> Iterator[None]:
    """Prevent importing heavy deps; purge already-loaded copies."""
    doomed = [key for key in list(sys.modules) if any(
        key == name or key.startswith(f"{name}.") for name in names
    )]
    saved = {key: sys.modules.pop(key) for key in doomed}

    class _Blocker:
        def find_spec(  # noqa: ANN001
            self,
            fullname: str,
            path: object = None,
            target: object = None,
        ) -> None:
            for name in names:
                if fullname == name or fullname.startswith(f"{name}."):
                    msg = f"blocked optional dependency: {fullname}"
                    raise ImportError(msg)
            return None

    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)  # type: ignore[arg-type]
    try:
        yield
    finally:
        if blocker in sys.meta_path:  # type: ignore[comparison-overlap]
            sys.meta_path.remove(blocker)  # type: ignore[arg-type]
        sys.modules.update(saved)


def _purge_package_modules(*prefixes: str) -> None:
    doomed = [
        key
        for key in list(sys.modules)
        if any(key == p or key.startswith(f"{p}.") for p in prefixes)
    ]
    for key in doomed:
        del sys.modules[key]


# ---------------------------------------------------------------------------
# AC: offline / uv-run builder from vendored Parquet (no Pyodide)
# ---------------------------------------------------------------------------


def test_build_derived_abdella_product_is_exportable() -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    assert callable(build)


def test_build_derived_abdella_product_writes_numpy_or_json_friendly_artifact(
    tmp_path: Path,
) -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    assert _ABDELLA_PARQUET.is_dir(), "vendored Abdella parquet tree required"
    out = tmp_path / "abdella_arrival_ages"
    result = build(_ABDELLA_PARQUET, out)
    out_path = Path(result)
    assert out_path.is_file(), f"builder must write an on-disk product at {out_path}"
    # Numpy- or JSON-friendly — not parquet.
    assert out_path.suffix.lower() in {".npz", ".json", ".npz.npz", ".npzz", ".npz.gz"}, (
        f"derived product must be numpy-/JSON-friendly, got {out_path.suffix!r}"
    )


def test_build_derived_abdella_product_missing_parquet_dir_raises(
    tmp_path: Path,
) -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    missing = tmp_path / "no_such_parquet"
    out = tmp_path / "out.npz"
    with pytest.raises((FileNotFoundError, NotADirectoryError, ValueError)):
        build(missing, out)


# ---------------------------------------------------------------------------
# AC: loader reads derived product without importing pyarrow
# ---------------------------------------------------------------------------


def test_load_derived_abdella_arrival_ages_is_exportable() -> None:
    load = _resolve_attr(
        "load_derived_abdella_arrival_ages",
        "load_derived_abdella",
        "load_arrival_age_product",
    )
    assert callable(load)


def test_load_derived_roundtrip_without_pyarrow(tmp_path: Path) -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    load = _resolve_attr(
        "load_derived_abdella_arrival_ages",
        "load_derived_abdella",
        "load_arrival_age_product",
    )
    artifact = Path(build(_ABDELLA_PARQUET, tmp_path / "product"))

    # Re-import loader path with pyarrow blocked after the desktop build step.
    _purge_package_modules("blueberries_voi.model", "blueberries_voi.data")
    with _block_modules("pyarrow"):
        load_fresh = _resolve_attr(
            "load_derived_abdella_arrival_ages",
            "load_derived_abdella",
            "load_arrival_age_product",
        )
        product = load_fresh(artifact)
    ages = _ages_from_product(product)
    assert ages.ndim == 1
    assert ages.size >= 1
    assert np.all(np.isfinite(ages))
    assert np.all(ages >= 0.0)


def test_load_derived_missing_path_raises(tmp_path: Path) -> None:
    load = _resolve_attr(
        "load_derived_abdella_arrival_ages",
        "load_derived_abdella",
        "load_arrival_age_product",
    )
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "missing_derived_product.npz")


# ---------------------------------------------------------------------------
# AC: injectable ages + product keys (abdella_all / long_haul / short_haul)
# ---------------------------------------------------------------------------


def test_arrival_age_loader_accepts_injectable_age_array() -> None:
    """Sim / session config can inject ages without touching parquet."""
    load_or_wrap = _resolve_attr(
        "arrival_ages_from_array",
        "load_arrival_ages",
        "ArrivalAgeProduct",
        "make_arrival_age_product",
    )
    ages = np.asarray([2.0, 4.5, 6.0], dtype=float)
    if isinstance(load_or_wrap, type):
        # Dataclass / NamedTuple constructor
        try:
            product = load_or_wrap(ages)  # type: ignore[misc]
        except TypeError:
            product = load_or_wrap(arrival_ages=ages)  # type: ignore[call-arg]
    else:
        try:
            product = load_or_wrap(ages)
        except TypeError:
            product = load_or_wrap(ages=ages)
    got = _ages_from_product(product)
    np.testing.assert_allclose(got, ages)


def test_arrival_age_loader_rejects_empty_injectable_ages() -> None:
    load_or_wrap = _resolve_attr(
        "arrival_ages_from_array",
        "load_arrival_ages",
        "make_arrival_age_product",
        "ArrivalAgeProduct",
    )
    empty = np.asarray([], dtype=float)
    with pytest.raises((ValueError, TypeError)):
        if isinstance(load_or_wrap, type):
            try:
                load_or_wrap(empty)  # type: ignore[misc]
            except TypeError:
                load_or_wrap(arrival_ages=empty)  # type: ignore[call-arg]
        else:
            try:
                load_or_wrap(empty)
            except TypeError:
                load_or_wrap(ages=empty)


def _load_with_key(load: Callable[..., Any], artifact: Path, product_key: str) -> Any:
    try:
        return load(artifact, product_key=product_key)
    except TypeError:
        return load(artifact, key=product_key)


@pytest.mark.parametrize("product_key", _PRODUCT_KEYS)
def test_product_key_selects_named_abdella_mix(product_key: str, tmp_path: Path) -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    load = _resolve_attr(
        "load_derived_abdella_arrival_ages",
        "load_derived_abdella",
        "load_arrival_age_product",
        "load_arrival_ages",
    )
    artifact = Path(build(_ABDELLA_PARQUET, tmp_path / f"product_{product_key}"))
    product = _load_with_key(load, artifact, product_key)
    ages = _ages_from_product(product)
    assert ages.size >= 1
    assert np.all(np.isfinite(ages))

    all_ages = _ages_from_product(_load_with_key(load, artifact, "abdella_all"))
    if product_key == "abdella_all":
        assert ages.size == 6, "abdella_all must cover all six MOD-21 shipments"
    elif product_key == "short_haul":
        # FL short-haul corridor (MOD-21): strict subset of the six-shipment mix.
        assert 1 <= ages.size < all_ages.size
        assert float(np.max(ages)) <= float(np.max(all_ages)) + 1e-9
    elif product_key == "long_haul":
        # CA→East long-haul corridor: complementary subset.
        assert 1 <= ages.size < all_ages.size
        assert float(np.min(ages)) >= float(np.min(all_ages)) - 1e-9


def test_unknown_product_key_rejected(tmp_path: Path) -> None:
    build = _resolve_attr("build_derived_abdella_product", "build_derived_abdella")
    load = _resolve_attr(
        "load_derived_abdella_arrival_ages",
        "load_derived_abdella",
        "load_arrival_age_product",
        "load_arrival_ages",
    )
    artifact = Path(build(_ABDELLA_PARQUET, tmp_path / "product"))
    with pytest.raises((KeyError, ValueError)):
        try:
            load(artifact, product_key="not_a_real_corridor")
        except TypeError:
            load(artifact, key="not_a_real_corridor")


def test_product_keys_constant_documents_three_named_mixes() -> None:
    keys = _resolve_attr(
        "PRODUCT_KEYS",
        "ARRIVAL_AGE_PRODUCT_KEYS",
        "ABDELLA_PRODUCT_KEYS",
    )
    key_set = set(keys) if not isinstance(keys, dict) else set(keys)
    for expected in _PRODUCT_KEYS:
        assert expected in key_set, f"missing documented product key {expected!r}"


# ---------------------------------------------------------------------------
# AC: browser entry / model helpers — no eager pyarrow / matplotlib
# ---------------------------------------------------------------------------


def test_browser_entry_module_importable_without_pyarrow_or_matplotlib() -> None:
    _purge_package_modules(
        "blueberries_voi.browser",
        "blueberries_voi.browser_entry",
        "blueberries_voi.model.abdella_product",
        "blueberries_voi.model.derived_abdella",
        "blueberries_voi.model.arrival_ages",
        "blueberries_voi.data",
    )
    with _block_modules("pyarrow", "matplotlib"):
        mod = _resolve_browser_entry()
        assert mod is not None
        # Loader helpers on the entry must still be reachable.
        has_loader = any(
            getattr(mod, name, None) is not None
            for name in (
                "load_derived_abdella_arrival_ages",
                "load_derived_abdella",
                "load_arrival_age_product",
                "load_arrival_ages",
                "arrival_ages_from_array",
                "BROWSER_ENTRY",
            )
        )
        assert has_loader, (
            f"{mod.__name__} must expose a derived-product / injectable "
            "arrival-age loader for the browser path"
        )


def test_browser_entry_source_has_no_eager_pyarrow_or_matplotlib() -> None:
    mod = _resolve_browser_entry()
    source = getattr(mod, "__file__", None)
    assert source is not None
    path = Path(source)
    assert path.is_file()
    forbidden = _imported_roots(path) & _FORBIDDEN_BROWSER_IMPORT_ROOTS
    assert not forbidden, (
        f"{path.name} must not eagerly import {sorted(forbidden)} "
        "(ADR 0099 / T-044 browser path)"
    )


def test_derived_product_module_does_not_import_abdella_parquet_io() -> None:
    """Break eager ``model.abdella`` parquet loaders on the interactive path."""
    mod = _resolve_product_module()
    source = getattr(mod, "__file__", None)
    assert source is not None
    tree = ast.parse(Path(source).read_text(encoding="utf-8"), filename=source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            joined = node.module
            if joined == "blueberries_voi.model.abdella" or joined.endswith(
                ".model.abdella"
            ):
                imported = {alias.name for alias in node.names}
                parquet_symbols = {
                    "load_abdella_shipments",
                    "default_abdella_root",
                    "pq",
                }
                overlap = imported & parquet_symbols
                assert not overlap, (
                    "derived product module must not eagerly import Abdella "
                    f"parquet I/O symbols {sorted(overlap)}"
                )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("pyarrow"), (
                    "derived product module must not import pyarrow"
                )


def test_filter_arrival_priors_lazy_or_free_of_eager_parquet_import() -> None:
    """Interactive filter path must not eagerly pull Abdella parquet I/O.

    Either ``filter.arrival_priors`` stops importing ``load_abdella_shipments``
    at module top-level, or a documented browser-safe prior helper lives on the
    derived-product module (injectable ages) without touching parquet.
    """
    priors_path = _SRC / "filter" / "arrival_priors.py"
    assert priors_path.is_file()
    tree = ast.parse(priors_path.read_text(encoding="utf-8"), filename=str(priors_path))

    def _top_level_abdella_parquet_import(module_ast: ast.AST) -> bool:
        for node in module_ast.body:  # type: ignore[attr-defined]
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.endswith("model.abdella") or node.module.endswith(
                    ".abdella"
                ):
                    names = {a.name for a in node.names}
                    if "load_abdella_shipments" in names:
                        return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
        return False

    eager = _top_level_abdella_parquet_import(tree)
    if not eager:
        return  # gated / removed — AC satisfied on the filter side

    # Still eager: browser path must offer injectable ages without that import.
    helper = _resolve_attr(
        "arrival_ages_from_array",
        "cold_abdella_arrival_ages_from_product",
        "arrival_age_prior_from_product",
        "load_arrival_ages",
    )
    assert callable(helper) or isinstance(helper, type)


# ---------------------------------------------------------------------------
# Packaged default product path (arrays / package data — no parquet on browser)
# ---------------------------------------------------------------------------


def test_default_packaged_derived_product_path_constant() -> None:
    path_const = _resolve_attr(
        "DEFAULT_DERIVED_ABDELLA_PATH",
        "DERIVED_ABDELLA_PRODUCT_PATH",
        "PACKAGED_ARRIVAL_AGE_PRODUCT",
    )
    path = Path(path_const) if not callable(path_const) else Path(path_const())
    assert path.suffix.lower() in {".npz", ".json", ".npz.npz", ".npzz", ".npz.gz", ""}
    # Constant may point at package data that implementer ships; existence is
    # required once the builder has been run into package data.
    assert "parquet" not in path.name.lower()
