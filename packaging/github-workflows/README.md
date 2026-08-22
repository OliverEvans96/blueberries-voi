# GitHub Actions workflow sources

Canonical workflow YAML lives in this directory. **Agents edit here only**; live
`.github/workflows/` is updated by a human so agent-dev-team protocol stays intact.

## Sync live workflows (required after packaging changes)

GitHub Actions does **not** run workflow files that are symlinks into `packaging/`.
Use real file copies:

```bash
./scripts/sync-github-workflows.sh
```

## CI layout (`ci.yml`)

Three parallel jobs on every push/PR:

| Job | What |
|-----|------|
| `rust` | `cargo test -p voi_core -p voi_py --locked` |
| `python` | `uv sync` (3.11), maturin develop, ruff, mypy, pytest+coverage |
| `web` | WASM build, vitest, `build:lib`, `npm pack` smoke |

On **main/master** pushes only, `deploy` runs after all three succeed (production
`npm run build` + dist artifact). PRs skip `deploy`.

`web-quality.yml` and `rust-kernel.yml` are **workflow_dispatch** stubs; gates live in CI.

## Release scope

- **Release studio** (`release-studio.yml`): WASM + `build:lib` + npm tarball after
  green **CI** on `main`/`master` (`workflow_run`), or on `studio-v*` tags. Vitest runs
  in CI `web`, not in release.
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present.
