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
| `build` | — | `uv sync --extra rust`, maturin wheel (`--release`), WASM (`--release`), `cargo test --release --no-run`; upload `ci-rust-wasm-build` (`target/release/` + WASM + wheels; 2-day retention) |
| `rust` | `build` | restore Cargo registry cache; download `ci-rust-wasm-build`; `cargo test --release` (prebuilt binaries) |
| `python` | `build` | download `ci-rust-wasm-build` (`target/release/` + PyO3 wheel); Rust toolchain for pytest `cargo test --release` subprocess only; unzip prebuilt `_core`; verify no `voi_*` recompile before pytest; ruff, mypy, pytest+coverage (`-m "not docs"`) |
| `docs` | — | `npm ci` in `docs/`, VitePress + `cargo doc` rustdoc bundle, docs/rustdoc guards, upload `docs-dist` (7-day retention) |
| `web` | `build` | download WASM from `ci-rust-wasm-build`; `build:lib`, vitest, `npm pack`; on main: `npm run build` + upload `studio-dist` (3-day retention) |

On **main/master** pushes only, `deploy` runs after `build`, `rust`, `python`, `web`, and
`docs` succeed. It downloads `studio-dist` and `docs-dist` to verify upstream artifacts,
then dispatches `blueberries-docs-published` to `OliverEvans96/personal-website` so the
site redeploys and serves the latest `/docs/blueberries/` bundle (`docs-dist` from the
`docs` job on that run).

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
| `blueberries-docs-published` | `ci.yml` `deploy` job | After green main CI; `docs-dist` from `docs` job on that run |
| `blueberries-studio-published` | `release-studio.yml` | After immutable `studio-v*` release (includes `client_payload.version`) |

`web-quality.yml` and `rust-kernel.yml` are **workflow_dispatch** stubs; gates live in CI.

## Studio PR previews (`studio-preview.yml`)

After a **green CI run on a same-repo pull request**, `studio-preview` deploys the
full studio app (`web/dist`) to Cloudflare Pages on branch `pr-{number}`. Preview
URLs follow `{branch}.{project}.pages.dev` (for example
`pr-42.blueberries-voi-studio.pages.dev`). The workflow posts or updates a PR comment
with the link.

When the PR **closes**, the `cleanup` job lists Cloudflare Pages deployments for
that preview branch and deletes them (`force=true`).

### Human setup (Cloudflare + Terraform)

1. Add **`CLOUDFLARE_API_TOKEN`** and **`CLOUDFLARE_ACCOUNT_ID`** to
   `secrets/secrets.enc.yaml` (see [`secrets/`](../secrets/)).
2. Run **`terraform apply`** with `enable_github_actions = true` to create the
   Pages project and sync GitHub secrets/variable:
   - Secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
   - Variable: `CLOUDFLARE_PAGES_PROJECT_NAME` (default project
     `blueberries-voi-studio`)
3. Sync live workflows after merge:
   `./scripts/sync-github-workflows.sh`

Fork PRs are skipped (`head_repository.full_name == github.repository`). The deploy
job downloads **`ci-rust-wasm-build`** from the triggering CI workflow run (same
artifact contract as `release-studio.yml`).

## Release scope

- **Release studio** (`release-studio.yml`): on green **CI** `workflow_run`, downloads
  `ci-rust-wasm-build` from that run (no WASM rebuild). Tag `studio-v*` pushes still
  build WASM locally. Then `build:lib` + npm tarball.
- **Python slim wheel**: **retired**. Delete the legacy `Release slim wheel` workflow
  from the live workflows directory if present.
