"""Studio PR preview workflow contracts (Cloudflare Pages)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PREVIEW_WORKFLOW = _REPO_ROOT / "packaging" / "github-workflows" / "studio-preview.yml"


def _job_block(text: str, job_name: str) -> str:
    match = re.search(rf"^  {re.escape(job_name)}:\n", text, flags=re.MULTILINE)
    assert match is not None, f"{job_name} job missing from studio-preview.yml"
    start = match.start()
    next_job = re.search(r"^  [a-z].*:\n", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_job.start() if next_job else len(text)
    return text[start:end]


def test_studio_preview_triggers_and_deploy_gates() -> None:
    """Deploy runs only after green same-repo PR CI workflow_run."""
    text = _PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    assert 'workflows: ["CI"]' in text
    assert "types: [completed]" in text
    assert "pull_request:" in text
    assert "types: [closed]" in text

    deploy = _job_block(text, "deploy")
    assert "github.event.workflow_run.conclusion == 'success'" in deploy
    assert "github.event.workflow_run.event == 'pull_request'" in deploy
    assert "head_repository.full_name == github.repository" in deploy


def test_studio_preview_deploy_downloads_ci_artifact_and_builds() -> None:
    """Deploy checks out workflow_run head and reuses ci-rust-wasm-build."""
    deploy = _job_block(_PREVIEW_WORKFLOW.read_text(encoding="utf-8"), "deploy")
    assert "ref: ${{ github.event.workflow_run.head_sha }}" in deploy
    assert "name: ci-rust-wasm-build" in deploy
    assert "run-id: ${{ github.event.workflow_run.id }}" in deploy
    assert "npm ci" in deploy
    assert "npm run build" in deploy
    assert "working-directory: web" in deploy


def test_studio_preview_deploy_uses_wrangler_with_pr_branch() -> None:
    """Wrangler deploy uses pr-{number} branch and repo Cloudflare names."""
    deploy = _job_block(_PREVIEW_WORKFLOW.read_text(encoding="utf-8"), "deploy")
    assert "uses: cloudflare/wrangler-action@v3" in deploy
    assert "pages deploy web/dist" in deploy
    assert "vars.CLOUDFLARE_PAGES_PROJECT_NAME" in deploy
    assert "secrets.CLOUDFLARE_API_TOKEN" in deploy
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in deploy
    assert re.search(
        r"(pr-\$\{\{\s*steps\.pr\.outputs\.number\s*\}\}|"
        r"\$\{\{\s*steps\.pr\.outputs\.branch\s*\}\})",
        deploy,
    ), "expected wrangler deploy branch pr-{number}"
    assert "--commit-dirty=true" in deploy


def test_studio_preview_deploy_posts_pr_comment() -> None:
    """Preview URL is posted back to the pull request."""
    deploy = _job_block(_PREVIEW_WORKFLOW.read_text(encoding="utf-8"), "deploy")
    assert "uses: peter-evans/create-or-update-comment@v4" in deploy
    assert "issue-number: ${{ steps.pr.outputs.number }}" in deploy
    assert "permissions:" in deploy
    assert "pull-requests: write" in deploy


def test_studio_preview_deploy_concurrency_is_per_pr() -> None:
    """Concurrent deploys for the same PR cancel in progress."""
    deploy = _job_block(_PREVIEW_WORKFLOW.read_text(encoding="utf-8"), "deploy")
    assert "group: studio-preview-pr-" in deploy
    assert "cancel-in-progress: true" in deploy


def test_studio_preview_cleanup_deletes_branch_deployments() -> None:
    """Closed PRs delete Cloudflare deployments on pr-{number} branch."""
    text = _PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    cleanup = _job_block(text, "cleanup")
    fork_guard = "github.event.pull_request.head.repo.full_name == github.repository"
    assert fork_guard in cleanup
    assert "secrets.CLOUDFLARE_API_TOKEN" in cleanup
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in cleanup
    assert "vars.CLOUDFLARE_PAGES_PROJECT_NAME" in cleanup
    assert "pr-${{ github.event.pull_request.number }}" in cleanup
    assert "curl" in cleanup
    assert "jq" in cleanup
    assert "DELETE" in cleanup
    assert "force=true" in cleanup
