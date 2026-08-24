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

Five jobs start in parallel; **rust**, **web**, and **python** wait on **build**:

| Job | Waits on | What |
|-----|----------|------|
| `build` | — | `uv sync --extra rust`, maturin wheel (`--release`), WASM (`--release`), `cargo test --release --no-run`; upload `ci-rust-wasm-build` |
| `rust` | `build` | restore Cargo registry cache; download `target/`; `cargo test --release` (prebuilt binaries) |
| `python` | `build` | download PyO3 wheel from `ci-rust-wasm-build`; `uv sync`; ruff, mypy, pytest+coverage (`-m "not docs"`) |
| `docs` | — | `npm ci` in `docs/`, VitePress + `cargo doc` rustdoc bundle, docs/rustdoc guards, upload `docs-dist` |
| `web` | `build` | download WASM from `ci-rust-wasm-build`; `build:lib`, vitest, `npm pack`; on main: `npm run build` + upload `studio-dist` |

On **main/master** pushes only, `deploy` runs after `build`, `rust`, `python`, `web`, and
`docs` succeed. It downloads `studio-dist` and `docs-dist` from those jobs, re-uploads
both artifacts, then dispatches `blueberries-docs-published` to
`OliverEvans96/personal-website` so the site redeploys and serves the latest
`/docs/blueberries/` bundle.

### Personal-website dispatch (human setup)

Cross-repo automation uses **`PERSONAL_WEBSITE_DISPATCH_PAT`** — provisioned via
SOPS + Terraform (see [`secrets/`](../secrets/) and [`terraform/`](../terraform/)),
not the GitHub UI.

1. Create a fine-grained PAT (or classic token) with **Contents: read** on
   `OliverEvans96/personal-website` and permission to trigger `repository_dispatch`.
2. Store the token in `secrets/secrets.enc.yaml` and run `terraform apply` with
   `enable_github_actions = true` to sync **`PERSONAL_WEBSITE_DISPATCH_PAT`** on
   this repo.
3. In `personal-website`, ensure workflows listen for:
   - `repository_dispatch` type **`blueberries-docs-published`** (docs redeploy)
   - `repository_dispatch` type **`blueberries-studio-published`** (studio semver bump PR)
4. After editing packaging YAML here, sync live workflows:
   `./scripts/sync-github-workflows.sh`

**Dispatch triggers:**

| Event | Workflow | When |
|-------|----------|------|
| `blueberries-docs-published` | `ci.yml` `deploy` job | After `studio-dist` + `docs-dist` upload on green main |
| `blueberries-studio-published` | `release-studio.yml` | After immutable `studio-v*` release (includes `client_payload.version`) |

`web-quality.yml` and `rust-kernel.yml` are **workflow_dispatch** stubs; gates live in CI.

## Release scope

- **Release studio** (`release-studio.yml`): on green **CI** `workflow_run`, downloads
  `ci-rust-wasm-build` from that run (no WASM rebuild). Tag `studio-v*` pushes still
  build WASM locally. Then `build:lib` + npm tarball.
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present.
