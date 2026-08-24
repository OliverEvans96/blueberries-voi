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

Five jobs start in parallel; only **rust** waits on **build**:

| Job | Waits on | What |
|-----|----------|------|
| `build` | — | `uv sync --extra rust`, maturin wheel (`--release`), WASM (`--release`), `cargo test --release --no-run`; upload `ci-rust-wasm-build` |
| `rust` | `build` | restore Cargo registry cache; download `target/`; `cargo test --release` (prebuilt binaries) |
| `python` | — | `uv sync`, `maturin develop`; ruff, mypy, pytest+coverage (`-m "not docs"`) |
| `docs` | — | `npm ci` in `docs/`, VitePress + `cargo doc` rustdoc bundle, docs/rustdoc guards, upload `docs-dist` |
| `web` | — | `build-wasm.sh`, `build:lib`, vitest, `npm pack` smoke |

On **main/master** pushes only, `deploy` runs after `build`, `rust`, `python`, `web`, and
`docs` succeed (production `npm run build` + `studio-dist`; docs site + `docs-dist`).

`web-quality.yml` and `rust-kernel.yml` are **workflow_dispatch** stubs; gates live in CI.

## Release scope

- **Release studio** (`release-studio.yml`): on green **CI** `workflow_run`, downloads
  `ci-rust-wasm-build` from that run (no WASM rebuild). Tag `studio-v*` pushes still
  build WASM locally. Then `build:lib` + npm tarball.
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present.
