# 0139. Vite-bundled WASM worker (T-144)

STATUS: ACCEPTED  
DATE: 2026-08-21  
SUPERSEDES: [0120](./0120-studio-wasm-adapter-third-host.md) (embed URL contract only)  
AMENDS: [0129](./0129-retire-pyodide-http-wasm-only-studio.md)

## Context

ADR 0120 placed the browser WASM host at `packaging/wasm/worker.js` with
wasm-pack output served from `/wasm/` via Vite dev middleware. Production builds
did not bundle the worker or `.wasm` binary — they relied on static paths outside
the Vite graph.

T-144 moves the worker into `web/src/engine/wasmWorker.ts` so dev **and**
`vite build` share one module graph.

## Decision

1. **Canonical worker:** `web/src/engine/wasmWorker.ts` (TypeScript, demo hydrate unchanged).
2. **wasm-pack output:** `web/src/wasm/` (gitignored); `./scripts/build-wasm.sh` also copies to `packaging/wasm/pkg/` for Node smoke/bench scripts.
3. **WasmAdapter default:** `new Worker(new URL("./wasmWorker.ts", import.meta.url), { type: "module" })`; worker imports `../wasm/voi_wasm.js` directly.
4. **Vite:** remove `servePackagingWasm()` middleware; enable worker ES format + `.wasm` asset handling.
5. **Env overrides (optional):** `VITE_WASM_WORKER_URL`, `VITE_WASM_ASSET_BASE_URL` (legacy `VITE_WASM_PKG_URL` honored) for CDN/legacy hosting only.
6. **Retire:** standalone `packaging/wasm/worker.js` (throws if loaded directly).

## Alternatives considered

- **Keep middleware + external worker in production** — rejected: breaks offline/CDN deploys; dev/prod divergence.
- **Symlink `web/public/wasm`** — rejected: still outside the module graph; no worker bundling.

## Consequences

**Easy:** one build artifact; no dev middleware drift; tests assert bundled worker URL.

**Hard:** developers must run `./scripts/build-wasm.sh` before first `npm run dev`; wasm output is gitignored under `web/src/wasm/`.

**Locked in:** default studio path needs no `VITE_WASM_*` URLs.
