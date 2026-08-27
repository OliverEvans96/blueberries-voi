"""T-148 — studio release workflow contracts."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "release-studio.yml"


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
