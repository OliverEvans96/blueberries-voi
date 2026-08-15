# Packaging

Browser and native build artifacts for blueberries-voi.

## Browser host (WASM only)

ADR [0129](../.team/adr/0129-retire-pyodide-http-wasm-only-studio.md) retires
the former Pyodide slim-wheel and FastAPI session paths. The **sole browser
host** is the Rust WASM kernel under [`wasm/`](wasm/):

| Artifact | Role |
|----------|------|
| `wasm/pkg/` | wasm-pack output served at `/wasm/` |
| `wasm/worker.js` | Web Worker RPC host (`init` / `step` / `act` / `set_obs_scenario`) |

Build and launch:

```bash
./scripts/build-wasm.sh
./scripts/studio.sh
```

See [`wasm/README.md`](wasm/README.md) for smoke tests and Vite URL defaults.

## Native Python extension

The `rust` extra (`maturin`) builds the PyO3 `EngineSession` used from
notebooks, CLI, and batch studies. This is separate from the browser WASM
artifact.

## Human: copy workflows into `.github/`

Agent protocol forbids writing live `.github/workflows/`. Canonical sources:

| Canonical | Live destination |
|-----------|------------------|
| `packaging/github-workflows/ci.yml` | `.github/workflows/ci.yml` |

Copy or symlink those files before CI jobs run on GitHub.
