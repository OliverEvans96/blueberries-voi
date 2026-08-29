"""T-148 — studio package version guard and release workflow contracts."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_JSON = _REPO_ROOT / "web" / "package.json"
_RELEASE_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "release-studio.yml"

_PUBLISHABLE_PREFIXES: tuple[str, ...] = (
    "web/src/",
    "web/vite.lib.config.ts",
    "web/scripts/",
    "crates/voi_core/",
    "crates/voi_wasm/",
    "scripts/build-wasm.sh",
)


def _merge_base_ref() -> str:
    base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base:
        return base if base.startswith("origin/") else f"origin/{base}"
    return "origin/main"


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_semver(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if match is None:
        msg = f"expected semver major.minor.patch, got {version!r}"
        raise ValueError(msg)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _semver_gt(left: str, right: str) -> bool:
    return _parse_semver(left) > _parse_semver(right)


def _read_package_version_at(ref: str) -> str:
    result = _run_git("show", f"{ref}:web/package.json")
    if result.returncode != 0:
        pytest.skip(f"cannot read web/package.json at {ref}: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    version = payload.get("version")
    assert isinstance(version, str)
    return version


def _changed_paths_vs_base(base_ref: str) -> list[str]:
    result = _run_git("diff", "--name-only", f"{base_ref}...HEAD")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        pytest.skip(f"cannot diff {base_ref}...HEAD: {detail}")
    return [line for line in result.stdout.splitlines() if line]


def _is_publishable_path(path: str) -> bool:
    for prefix in _PUBLISHABLE_PREFIXES:
        normalized = prefix.rstrip("/")
        if path == normalized or path.startswith(prefix):
            return True
    return False


def _publishable_paths_changed(base_ref: str) -> bool:
    return any(_is_publishable_path(path) for path in _changed_paths_vs_base(base_ref))


def test_studio_package_version_is_1_0_1() -> None:
    """Release semver pinned for studio embed package."""
    payload = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))
    assert payload["version"] == "1.0.1"


def test_publishable_path_changes_require_strict_version_bump() -> None:
    """AC-version-guard: publishable diffs must bump web/package.json semver."""
    base_ref = _merge_base_ref()
    if not _publishable_paths_changed(base_ref):
        pytest.skip(f"no publishable path changes vs {base_ref}")

    head_version = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
    base_version = _read_package_version_at(base_ref)
    assert _semver_gt(head_version, base_version), (
        "publishable studio paths changed vs merge-base but "
        f"web/package.json version did not strictly increase "
        f"({base_version!r} -> {head_version!r}); bump semver per T-148"
    )


def test_release_workflow_auto_creates_studio_v_on_workflow_run() -> None:
    """AC-immutable-release: workflow_run path cuts studio-v{version} when absent."""
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "studio-v" in text
    assert "workflow_run" in text
    assert re.search(r"studio-v\$\{\{\s*steps\.pkg\.outputs\.version\s*\}\}", text), (
        "expected studio-v${{ steps.pkg.outputs.version }} tag pattern"
    )
    assert re.search(r"exists\s*==\s*['\"]false['\"]", text), (
        "expected guard that skips when studio-v tag already exists"
    )


def test_studio_v_releases_attach_versioned_tarball_only() -> None:
    """AC-immutable-assets: studio-v* releases must not upload -latest.tgz alias."""
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "Publish immutable studio-v" in text, (
        "expected dedicated immutable studio-v release step(s)"
    )
    blocks = re.split(r"- name: Publish immutable studio-v", text)[1:]
    assert blocks, "immutable studio-v publish steps missing"
    for block in blocks:
        assert "oliverevans96-blueberries-voi-studio-latest.tgz" not in block, (
            "immutable studio-v release must not attach -latest.tgz alias"
        )
        assert "make_latest: false" in block, (
            "immutable studio-v release must not become GitHub latest"
        )
