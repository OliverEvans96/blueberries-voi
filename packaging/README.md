# Packaging

ADR [0129](../.team/adr/0129-retire-pyodide-http-wasm-only-studio.md) locks the
browser studio to a **single host**: the Rust WASM kernel under
`packaging/wasm/`. There is no slim Pyodide wheel, no `micropip` install path,
and no FastAPI session API for the studio.

## Browser studio (WASM)

| Piece | Location |
|-------|----------|
| Worker RPC | `packaging/wasm/worker.js` |
| wasm-pack output | `packaging/wasm/pkg/` (served at `/wasm/` in dev) |
| Build | `./scripts/build-wasm.sh` |
| Smoke | `./scripts/smoke-wasm.sh` |
| Launch | `./scripts/studio.sh` |

Details: [`packaging/wasm/README.md`](wasm/README.md).

Derived Abdella arrival ages ship as package data
(`blueberries_voi/data/abdella_arrival_ages.npz`) for native Python workflows.

## Native Python (notebooks / CLI)

Notebooks, sweep, bootstrap, and CLI continue to use the PyO3 `EngineSession`
in `src/blueberries_voi/simulator/`. Optional extras in `pyproject.toml`:

| Extra | Use |
|-------|-----|
| `data` | pyarrow (Abdella Parquet / Gate 0) |
| `viz` | matplotlib (static figures) |
| `rust` | maturin (PyO3 extension builds) |

## Human: copy workflows into `.github/`

Agent protocol forbids writing live `.github/workflows/`. Canonical sources:

| Canonical | Live destination |
|-----------|------------------|
| `packaging/github-workflows/ci.yml` | `.github/workflows/ci.yml` |
| `packaging/github-workflows/rust-kernel.yml` | `.github/workflows/rust-kernel.yml` |
| `packaging/github-workflows/web-quality.yml` | `.github/workflows/web-quality.yml` |
| `packaging/github-workflows/release-studio.yml` | `.github/workflows/release-studio.yml` |

Use **real file copies** only — symlinked workflow YAML is not executed by
GitHub Actions.

**Retired:** slim Python wheel release workflow (ADR 0129; studio is WASM-only).

**Prod studio tarball:** after the studio release workflow is live, releases run
only after **CI** succeeds on `main`. Each green run rebuilds the moving tag
`studio-latest` (versioned tgz + `-latest.tgz` alias; see EMBEDDING.md). The
same run auto-cuts **`studio-v{version}`** when that tag is absent (versioned
tgz only, `make_latest: false`). Manual immutable pins use `studio-v*` tag
pushes.

**Version policy:** bump `web/package.json` semver whenever publishable studio
paths change (`web/src/`, `web/vite.lib.config.ts`, `web/scripts/`,
`crates/voi_core/`, `crates/voi_wasm/`, `scripts/build-wasm.sh`). Guard:
`tests/test_studio_release_version.py`.
