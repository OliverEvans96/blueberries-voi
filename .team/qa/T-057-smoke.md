# T-057 smoke checklist — studio adapter wiring

Pass / fail checklist for wiring the D3 studio off fake JS physics onto the
**WasmAdapter** (Rust kernel in the browser, ADR 0129).

## Env flags

| Variable | Purpose |
|----------|---------|
| `VITE_ENGINE_ADAPTER` | Explicit override: `wasm` \| `mock` (debug only) |
| `VITE_WASM_WORKER_URL` | WASM worker script URL (default `/packaging/wasm/worker.js`) |
| `VITE_WASM_PKG_URL` | wasm-pack output base URL (default `/wasm/`) |

Selection rules (`resolveStudioAdapterKind`):

1. `VITE_ENGINE_ADAPTER` wins when set to `wasm` / `mock`
2. Else default → **wasm**
3. `mock` only when explicitly selected

## WASM studio (default)

- [ ] `./scripts/build-wasm.sh` (if `packaging/wasm/pkg` is missing)
- [ ] `./scripts/studio.sh` or `cd web && npm run studio`
- [ ] Studio footer shows live WASM (not fake / mock data)
- [ ] Advance calls `adapter.step_n` (worker RPC, not `generate.ts`)
- [ ] Reset calls `adapter.reset`; bootstrap called `adapter.init`
- [ ] Economics sliders update charts without network (projector `setEconomics` only)
- [ ] Worker URL resolves to `/packaging/wasm/worker.js` with `pkgUrl=/wasm/`

**Pass / fail:** ________

## Debug Mock (optional)

- [ ] `VITE_ENGINE_ADAPTER=mock` keeps **MockAdapter** as an explicit debug option
- [ ] Without that override, default path is never Mock

**Pass / fail:** ________
