"""Slim/browser wheel numpy must accept Pyodide 314.0.4's bundled numpy.

Pyodide 314.0.4 ``loadPackage("numpy")`` installs numpy 2.4.3. micropip then
installs the slim wheel; if METADATA still asks for ``numpy>=2.4.6``, init
fails with ValueError and must not be "fixed" by reinstalling a CPython numpy.

Native / CPython packaging (``pyproject.toml`` + ``uv.lock``) keeps
``numpy>=2.4.6``. Only the slim wheel / worker path is retargeted.
"""

from __future__ import annotations

import re
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

from blueberries_voi.slim_wheel_metadata import rewrite_hard_numpy_requires

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_UV_LOCK = _REPO_ROOT / "uv.lock"
_BUILDER = _REPO_ROOT / "scripts" / "build_slim_wheel.py"
_WORKER_JS = _REPO_ROOT / "packaging" / "pyodide" / "worker.js"

# Fixture METADATA as setuptools would emit before the slim-wheel rewrite.
_UNREWRITTEN_METADATA = """\
Metadata-Version: 2.1
Name: blueberries-voi
Version: 0.1.0
Requires-Dist: numpy>=2.4.6
Requires-Dist: scipy>=1.17.1
Requires-Dist: pyarrow>=25.0.1; extra == "data"
"""

# Pyodide 314.0.4 full index: numpy-2.4.3-cp314-*-pyemscripten_2026_0_wasm32.whl
_PYODIDE_PIN = "314.0.4"
_PYODIDE_BUNDLED_NUMPY = "2.4.3"
_NATIVE_NUMPY_FLOOR = "2.4.6"

_EMSCRIPTEN_ENV = {
    "sys_platform": "emscripten",
    "platform_machine": "wasm32",
    "python_version": "3.14",
    "python_full_version": "3.14.0",
    "os_name": "posix",
    "platform_system": "Emscripten",
    "implementation_name": "cpython",
    "extra": "",
}


def _strip_js_comments(src: str) -> str:
    no_block = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"^\s*//.*$", "", no_block, flags=re.MULTILINE)


def _find_built_slim_wheels() -> list[Path]:
    found: list[Path] = []
    for folder in (
        _REPO_ROOT / "dist",
        _REPO_ROOT / "packaging" / "dist",
        _REPO_ROOT / "artifacts" / "wheels",
    ):
        if folder.is_dir():
            found.extend(sorted(folder.glob("blueberries_voi-*.whl")))
    return found


def _wheel_metadata(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as zf:
        meta_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        assert meta_names, f"no METADATA in {wheel.name}"
        return zf.read(meta_names[0]).decode("utf-8")


def _hard_requires_dist(meta: str) -> list[Requirement]:
    reqs: list[Requirement] = []
    for line in meta.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        spec = line.split(":", 1)[1].strip()
        req = Requirement(spec)
        if req.marker is not None and "extra" in str(req.marker).lower():
            continue
        reqs.append(req)
    return reqs


def _numpy_reqs_for_emscripten(reqs: list[Requirement]) -> list[Requirement]:
    out: list[Requirement] = []
    for req in reqs:
        if req.name.lower() != "numpy":
            continue
        if req.marker is not None and not req.marker.evaluate(_EMSCRIPTEN_ENV):
            continue
        out.append(req)
    return out


def _core_numpy_specs() -> list[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    assert isinstance(deps, list)
    return [str(d) for d in deps if str(d).lower().startswith("numpy")]


def test_native_pyproject_keeps_numpy_2_4_6_floor() -> None:
    """CPython / uv / CI 3.11 pin stays numpy>=2.4.6 (not globally dropped)."""
    specs = _core_numpy_specs()
    assert specs, "pyproject.toml must declare a core numpy dependency"
    blob = " ".join(specs)
    assert _NATIVE_NUMPY_FLOOR in blob, (
        "native project.dependencies must keep numpy>="
        f"{_NATIVE_NUMPY_FLOOR}; got {specs}"
    )
    for spec in specs:
        req = Requirement(spec)
        if req.marker is not None and not req.marker.evaluate(
            {"sys_platform": "linux", "extra": ""}
        ):
            continue
        assert Version(_NATIVE_NUMPY_FLOOR) in req.specifier, (
            f"native numpy specifier {spec!r} must accept {_NATIVE_NUMPY_FLOOR}"
        )
        assert Version(_PYODIDE_BUNDLED_NUMPY) not in req.specifier or (
            req.marker is not None and "emscripten" in str(req.marker)
        ), (
            "do not globally lower native numpy to Pyodide's 2.4.3; "
            f"got {spec!r}. Retarget the slim wheel METADATA instead."
        )


def test_uv_lock_keeps_native_numpy_specifier() -> None:
    text = _UV_LOCK.read_text(encoding="utf-8")
    assert f'specifier = ">={_NATIVE_NUMPY_FLOOR}"' in text, (
        "uv.lock must keep the native numpy>="
        f"{_NATIVE_NUMPY_FLOOR} specifier; do not retarget the lock for Pyodide"
    )


def test_slim_wheel_builder_retargets_numpy_for_pyodide_bundled() -> None:
    """build_slim_wheel.py must rewrite slim METADATA for Pyodide 314 numpy 2.4.3."""
    assert _BUILDER.is_file(), f"missing {_BUILDER}"
    src = _BUILDER.read_text(encoding="utf-8")
    helper_path = _REPO_ROOT / "src" / "blueberries_voi" / "slim_wheel_metadata.py"
    helper = helper_path.read_text(encoding="utf-8")
    assert "rewrite_hard_numpy_requires" in src
    assert _PYODIDE_BUNDLED_NUMPY in helper, (
        "slim wheel builder must retarget numpy Requires-Dist to accept "
        f"Pyodide {_PYODIDE_PIN} bundled numpy {_PYODIDE_BUNDLED_NUMPY} "
        "(do not change native pyproject.toml)"
    )
    assert re.search(r"Requires-Dist|METADATA|emscripten", helper), (
        "builder must rewrite wheel METADATA (or emscripten marker), not "
        "the native CPython pin"
    )


def test_slim_wheel_metadata_accepts_pyodide_314_bundled_numpy() -> None:
    """micropip on Pyodide must accept loadPackage numpy 2.4.3 without reinstall."""
    meta = rewrite_hard_numpy_requires(_UNREWRITTEN_METADATA)
    reqs = _hard_requires_dist(meta)
    numpy_reqs = _numpy_reqs_for_emscripten(reqs)
    assert numpy_reqs, "rewritten METADATA lacks emscripten numpy Requires-Dist"
    assert 'extra == "data"' in meta
    bundled = Version(_PYODIDE_BUNDLED_NUMPY)
    for req in numpy_reqs:
        assert bundled in req.specifier, (
            f"numpy requirement {req} rejects Pyodide "
            f"{_PYODIDE_PIN} bundled numpy=={_PYODIDE_BUNDLED_NUMPY}. "
            "Rewrite slim-wheel METADATA only; do not micropip reinstall "
            "a CPython numpy."
        )
    wheels = _find_built_slim_wheels()
    if not wheels:
        return
    wheel = wheels[0]
    built_reqs = _numpy_reqs_for_emscripten(_hard_requires_dist(_wheel_metadata(wheel)))
    assert built_reqs, f"{wheel.name} has no hard numpy Requires-Dist on emscripten"
    for req in built_reqs:
        assert bundled in req.specifier, (
            f"{wheel.name} numpy requirement {req} rejects bundled numpy "
            f"{_PYODIDE_BUNDLED_NUMPY}"
        )


def test_slim_wheel_keeps_native_numpy_floor_off_emscripten() -> None:
    """CPython install of the slim wheel still requires numpy>=2.4.6."""
    linux_env = {**_EMSCRIPTEN_ENV, "sys_platform": "linux", "platform_system": "Linux"}
    meta = rewrite_hard_numpy_requires(_UNREWRITTEN_METADATA)
    reqs = [
        req
        for req in _hard_requires_dist(meta)
        if req.name.lower() == "numpy"
        and (req.marker is None or req.marker.evaluate(linux_env))
    ]
    assert reqs, "rewritten METADATA must declare numpy off emscripten"
    native = Version(_NATIVE_NUMPY_FLOOR)
    bundled = Version(_PYODIDE_BUNDLED_NUMPY)
    for req in reqs:
        assert native in req.specifier, (
            f"non-emscripten numpy requirement {req} must keep >={_NATIVE_NUMPY_FLOOR}"
        )
        assert bundled not in req.specifier, (
            f"do not lower the CPython numpy floor in slim METADATA; got {req}"
        )
    wheels = _find_built_slim_wheels()
    if not wheels:
        return
    built = [
        req
        for req in _hard_requires_dist(_wheel_metadata(wheels[0]))
        if req.name.lower() == "numpy"
        and (req.marker is None or req.marker.evaluate(linux_env))
    ]
    assert built, "slim wheel must still declare numpy for non-emscripten installs"
    for req in built:
        assert native in req.specifier
        assert bundled not in req.specifier


def test_worker_reuses_loadpackage_numpy_without_reinstall() -> None:
    """Worker must loadPackage Pyodide numpy; never micropip reinstall=True."""
    assert _WORKER_JS.is_file(), f"missing {_WORKER_JS}"
    src = _strip_js_comments(_WORKER_JS.read_text(encoding="utf-8"))
    assert re.search(
        r"""loadPackage\s*\(\s*\[[^\]]*["']numpy["']""",
        src,
    ), "worker must loadPackage numpy (Pyodide bundled wheel)"
    assert not re.search(r"reinstall\s*[:=]\s*True", src), (
        "do not micropip.install(..., reinstall=True) a PyPI numpy into Pyodide"
    )
    assert _PYODIDE_PIN in _WORKER_JS.read_text(encoding="utf-8")


def test_worker_loadpackage_includes_pyarrow_for_eager_abdella_import() -> None:
    """sim.shipments imports model.abdella (pyarrow) at module load; init needs it."""
    src = _strip_js_comments(_WORKER_JS.read_text(encoding="utf-8"))
    assert "ensure_demo_shipments" in src or "abdella" in src.lower()
    assert re.search(
        r"""loadPackage\s*\(\s*\[[^\]]*["']pyarrow["']""",
        src,
    ), (
        "worker must loadPackage pyarrow (Pyodide's own build) because "
        "ensure_demo_shipments → model.abdella imports pyarrow at module load. "
        "Do not micropip a CPython pyarrow wheel."
    )
    assert re.search(
        r"""loadPackage\s*\(\s*\[[^\]]*["']scipy["']""",
        src,
    ), "worker must keep loadPackage scipy (Pyodide bundled)"
