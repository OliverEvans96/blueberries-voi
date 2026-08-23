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

One **build** job compiles Rust (native + PyO3 wheel), WASM (`build-wasm.sh`), and
runs `cargo test` once. It uploads `ci-rust-wasm-build` (target/, WASM pkg dirs,
`dist/wheels/`).

Three parallel test jobs consume that artifact:

| Job | What |
|-----|------|
| `build` | maturin wheel, WASM, `cargo test`; upload artifacts |
| `rust` | download `target/`; `cargo test` (prebuilt) |
| `python` | `uv sync`, `maturin develop` with shared `target/; ruff, mypy, pytest+coverage |
| `web` | prebuilt WASM; vitest, `build:lib`, `npm pack` smoke |

On **main/master** pushes only, `deploy` runs after all three test jobs succeed
(production `npm run build` + dist artifact; WASM from CI artifact).

`web-quality.yml` and `rust-kernel.yml` are **workflow_dispatch** stubs; gates live in CI.

## Release scope

- **Release studio** (`release-studio.yml`): on green **CI** `workflow_run`, downloads
  `ci-rust-wasm-build` from that run (no WASM rebuild). Tag `studio-v*` pushes still
  build WASM locally. Then `build:lib` + npm tarball.
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present.
