# T-057 smoke checklist — studio adapter wiring

Pass / fail checklist for wiring the D3 studio off fake JS physics onto real
adapters (dev = **HttpAdapter**, prod = **PyodideAdapter**).

## Env flags

| Variable | Purpose |
|----------|---------|
| `VITE_ENGINE_ADAPTER` | Explicit override: `http` \| `pyodide` \| `mock` (debug only) |
| `VITE_ENGINE_API_BASE_URL` | Preferred ASGI base URL for HttpAdapter |
| `VITE_API_BASE_URL` | Fallback ASGI base URL |
| `VITE_PYODIDE_WORKER_URL` | Pyodide worker script URL (default `/packaging/pyodide/worker.js`) |
| `VITE_PYODIDE_WHEEL_URL` | Release/slim wheel URL for micropip |

Selection rules (`resolveStudioAdapterKind`):

1. `VITE_ENGINE_ADAPTER` wins when set to `http` / `pyodide` / `mock`
2. Else production (`PROD` / `MODE=production`) → **pyodide**
3. Else development with an API base URL → **http**
4. `mock` only when explicitly selected

## Dev / HttpAdapter

- [ ] `cd web && VITE_ENGINE_API_BASE_URL=http://127.0.0.1:8000 npm run dev`
- [ ] Local ASGI session API is running on that base URL
- [ ] Studio loads; Advance calls `adapter.step` (network to `/sessions/.../step`)
- [ ] Reset calls `adapter.reset`; bootstrap called `adapter.init`
- [ ] Economics sliders update charts without network (projector `setEconomics` only)
- [ ] No `generate.ts` / fake day-loop on the Advance path

**Pass / fail:** ________

## Prod / PyodideAdapter

- [ ] `cd web && npm run build && npm run preview` (or production MODE)
- [ ] Worker + wheel URLs resolve (`VITE_PYODIDE_*` or package defaults)
- [ ] Studio constructs **PyodideAdapter** (worker starts; no HttpAdapter traffic)
- [ ] Advance / Reset / init return Snapshot / DayDelta via worker RPC
- [ ] Economics remain local via projector

**Pass / fail:** ________

## Debug Mock (optional)

- [ ] `VITE_ENGINE_ADAPTER=mock` keeps **MockAdapter** as an explicit debug option
- [ ] Without that override, default path is never Mock

**Pass / fail:** ________
