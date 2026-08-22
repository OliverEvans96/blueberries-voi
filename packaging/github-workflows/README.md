# GitHub Actions workflow sources

Canonical workflow YAML lives in this directory. **Agents edit here only**; live
`.github/workflows/` is updated by a human so agent-dev-team protocol stays intact.

## Sync live workflows (required after packaging changes)

GitHub Actions does **not** run workflow files that are symlinks into `packaging/`.
Use real file copies:

```bash
./scripts/sync-github-workflows.sh
```

## Release scope

- **Release studio** (`release-studio.yml`): React/WASM studio tarball only (`studio-v*`
  tags and `studio-latest` after green CI on `main`/`master`).
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present; releases do not build Python wheels.

## CI Python / maturin

The **CI** quality job uses `uv sync` plus `maturin develop` for the optional native
extension in tests. That is not a wheel publish step and does not run on release.
