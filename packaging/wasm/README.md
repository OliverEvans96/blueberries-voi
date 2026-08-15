# WASM studio kernel

The **sole browser host** for the interactive store studio (ADR 0129). Vite
serves this worker and the wasm-pack output; there is no HTTP session API or
in-browser Python path.

Build (requires rustc + wasm-pack; no C cross-compiler or clang needed):

```bash
./scripts/build-wasm.sh
```

WASM smoke (builds **wasm32** via wasm-pack `--target nodejs`, then Node
`handle_rpc` for init / reset / step / step_n / act plus error envelopes).
Fails unless `result.belief.lot_counts` is a defined array (`"ok": true`
alone is not enough):

```bash
./scripts/smoke-wasm.sh
```

Launch the studio after a build:

```bash
./scripts/studio.sh
```

Vite serves `packaging/wasm/pkg/` at `/wasm/` (`VITE_WASM_PKG_URL=/wasm/`).
The worker is `packaging/wasm/worker.js` (`VITE_WASM_WORKER_URL`).
