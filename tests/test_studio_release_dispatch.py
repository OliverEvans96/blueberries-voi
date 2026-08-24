"""T-159 / GH #12 — personal-website dispatch after immutable studio-v releases."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "release-studio.yml"

_IMMUTABLE_MARKER = "Publish immutable studio-v"
_DISPATCH_STEP = "Notify personal-website of studio release"


def _release_job_block(text: str) -> str:
    match = re.search(r"^  release:\n", text, flags=re.MULTILINE)
    assert match is not None, (
        "release job missing from packaging/github-workflows/release-studio.yml"
    )
    return text[match.start() :]


def _step_index(block: str, step_name: str) -> int:
    pattern = re.compile(rf"^\s+- name: {re.escape(step_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(block)
    assert match is not None, f"step {step_name!r} missing from release job"
    return match.start()


def test_immutable_studio_v_release_dispatches_personal_website() -> None:
    """AC-studio-dispatch: immutable studio-v triggers blueberries-studio-published."""
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    release = _release_job_block(text)

    marker = re.escape(_IMMUTABLE_MARKER)
    immutable_blocks = list(
        re.finditer(rf"^\s+- name: {marker}", release, flags=re.MULTILINE)
    )
    assert immutable_blocks, "expected immutable studio-v publish step(s)"

    dispatch_idx = _step_index(release, _DISPATCH_STEP)
    last_immutable_idx = immutable_blocks[-1].start()
    assert last_immutable_idx < dispatch_idx, (
        "studio dispatch must run after immutable studio-v publish step(s)"
    )

    dispatch_block = release[dispatch_idx : dispatch_idx + 800]
    assert "uses: peter-evans/repository-dispatch@v3" in dispatch_block
    assert "secrets.PERSONAL_WEBSITE_DISPATCH_PAT" in dispatch_block
    assert "repository: OliverEvans96/personal-website" in dispatch_block
    assert "event-type: blueberries-studio-published" in dispatch_block
    assert "client-payload" in dispatch_block
    assert "steps.pkg.outputs.version" in dispatch_block
    assert "continue-on-error" not in dispatch_block, (
        "studio dispatch step must not use continue-on-error"
    )


def test_studio_dispatch_does_not_run_after_studio_latest_only() -> None:
    """AC-studio-dispatch-scope: dispatch is gated to immutable studio-v paths."""
    text = _RELEASE_WORKFLOW.read_text(encoding="utf-8")
    release = _release_job_block(text)
    dispatch_block = release[_step_index(release, _DISPATCH_STEP) :]

    assert "Publish studio-latest" not in dispatch_block, (
        "studio dispatch must not be tied to studio-latest publish step"
    )
    assert "steps.imm.outputs.exists == 'false'" in dispatch_block.replace('"', "'"), (
        "studio dispatch must gate workflow_run path to new immutable studio-v tag"
    )
    assert "startsWith(github.ref, 'refs/tags/studio-v')" in dispatch_block, (
        "studio dispatch must gate tag-push path to studio-v* tags"
    )
