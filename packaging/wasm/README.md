# WASM studio kernel

The **sole browser host** for the interactive store studio (ADR 0129). As of
**T-144 / ADR 0139**, the worker lives at `web/src/engine/wasmWorker.ts` and is
bundled by Vite; wasm-pack output lands in `web/src/wasm/` (gitignored).

Build (requires rustc + wasm-pack; no C cross-compiler or clang needed):

```bash
./scripts/build-wasm.sh
```

This writes `web/src/wasm/` and copies the same artifacts to `packaging/wasm/pkg/`
for Node smoke/bench scripts that still import from the legacy path.

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

**Default (T-144):** no `VITE_WASM_*` URLs — Vite bundles the worker and wasm
pkg. Optional overrides for CDN hosting:

- `VITE_WASM_WORKER_URL` — external worker script
- `VITE_WASM_ASSET_BASE_URL` — external wasm pkg base (legacy `VITE_WASM_PKG_URL` still honored)

The retired standalone `packaging/wasm/worker.js` is replaced by
`web/src/engine/wasmWorker.ts`.
