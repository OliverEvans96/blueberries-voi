# T-148 QA — RED test map

Track **T-148** / branch `team/T-148/qa`. Guard and workflow contract tests from
`.team/specs/T-148.md` before implement bumps version and edits release workflow.

## Coverage of acceptance criteria

- **AC-first-bump (`version` → `0.1.1`)** →
  `tests/test_studio_release_version.py::test_studio_package_version_is_0_1_1` —
  currently failing: `web/package.json` still `0.1.0`.

- **AC-version-guard (publishable diff ⇒ strict semver bump)** →
  `tests/test_studio_release_version.py::test_publishable_path_changes_require_strict_version_bump` —
  skips when no publishable paths changed vs merge-base; fails when they did
  and version did not strictly increase.

- **AC-immutable-release (workflow_run auto `studio-v{version}`)** →
  `tests/test_studio_release_version.py::test_release_workflow_auto_creates_studio_v_on_workflow_run` —
  currently failing: draft workflow has no auto-cut immutable tag step.

- **AC-immutable-assets (`studio-v*` = versioned tgz only)** →
  `tests/test_studio_release_version.py::test_studio_v_releases_attach_versioned_tarball_only` —
  currently failing: single release step uploads both versioned and `-latest.tgz`
  for all paths.

## Not covered by tests

- Live `.github/workflows/release-studio.yml` sync (human step).
- End-to-end GitHub Actions run (verify uses static workflow text assertions).
- `EMBEDDING.md` / `packaging/README.md` prose (review + verify human read).

## RED proof

```bash
cd .worktrees/T-148-qa
uv run pytest tests/test_studio_release_version.py --no-cov -v
```

Expected: 3 failures (`test_studio_package_version_is_0_1_1`,
`test_release_workflow_auto_creates_studio_v_on_workflow_run`,
`test_studio_v_releases_attach_versioned_tarball_only`); 1 skip or pass on
version-guard depending on diff vs `origin/main`.
