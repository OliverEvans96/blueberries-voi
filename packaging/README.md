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

Copy or symlink those files before CI jobs run on GitHub.

Studio npm releases use tags `studio-v*` (e.g. `studio-v0.1.0`) so they do not
 collide with the legacy Python `v*` wheel workflow. See [`EMBEDDING.md`](../EMBEDDING.md)
 for Astro / Vite consumer wiring.
