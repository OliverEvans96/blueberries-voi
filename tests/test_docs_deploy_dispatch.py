"""T-159 — personal-website repository-dispatch when docs-dist publishes."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "ci.yml"

_DISPATCH_STEP_NAME = "Notify personal-website to redeploy docs"
_STUDIO_UPLOAD = "Upload studio dist artifact"
_DOCS_UPLOAD = "Upload docs dist artifact"


def _deploy_job_block(text: str) -> str:
    match = re.search(r"^  deploy:\n", text, flags=re.MULTILINE)
    assert match is not None, (
        "deploy job missing from packaging/github-workflows/ci.yml"
    )
    return text[match.start() :]


def _step_index(block: str, step_name: str) -> int:
    pattern = re.compile(rf"^\s+- name: {re.escape(step_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(block)
    assert match is not None, f"step {step_name!r} missing from deploy job"
    return match.start()


def test_deploy_job_dispatches_personal_website_after_docs_dist() -> None:
    """AC-dispatch-step + AC-step-order + AC-main-only: dispatch after uploads."""
    text = _CI_WORKFLOW.read_text(encoding="utf-8")
    deploy = _deploy_job_block(text)

    main_gate = (
        "if: github.event_name == 'push' && "
        "(github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master')"
    )
    assert main_gate in deploy, "deploy job must remain main/master push gated"

    studio_idx = _step_index(deploy, _STUDIO_UPLOAD)
    docs_idx = _step_index(deploy, _DOCS_UPLOAD)
    dispatch_idx = _step_index(deploy, _DISPATCH_STEP_NAME)
    assert studio_idx < docs_idx < dispatch_idx, (
        "dispatch step must follow studio-dist and docs-dist upload steps"
    )

    dispatch_block = deploy[dispatch_idx : dispatch_idx + 600]
    assert "uses: peter-evans/repository-dispatch@v3" in dispatch_block
    assert "secrets.PERSONAL_WEBSITE_DISPATCH_PAT" in dispatch_block
    assert "repository: OliverEvans96/personal-website" in dispatch_block
    assert "event-type: blueberries-docs-published" in dispatch_block
    assert "continue-on-error" not in dispatch_block, (
        "dispatch step must not use continue-on-error"
    )
