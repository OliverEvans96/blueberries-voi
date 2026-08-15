# T-125 qa-studio shard — RED map (vitest)

Shard: **qa-studio** (Wave 1). Parent: `team/T-125/architect` @ `3bcccd6`.

Gate command:

```bash
cd web && npm test -- --run src/engine/studioAdapter.test.ts src/engine/studioWiring.test.ts src/engine/studioFooterEnv.test.ts
```

**Status:** RED — 19 failed / 21 passed (2026-08-15).

## Coverage of acceptance criteria

### AC-studio — Studio defaults to WASM

- `resolveStudioAdapterKind()` returns `"wasm"` when `VITE_ENGINE_ADAPTER` is unset in both dev and prod → `studioAdapter.test.ts::returns wasm when VITE_ENGINE_ADAPTER is unset` — currently failing: returns `"pyodide"`
- prod default wasm not pyodide → `studioAdapter.test.ts::returns wasm in production when override is unset (not pyodide)` — currently failing: returns `"pyodide"`
- dev with API base still wasm (not http) → `studioAdapter.test.ts::returns wasm in dev when API base is configured (not http)` — currently failing: returns `"http"`
- `StudioAdapterKind` is `"wasm" | "mock"` only → `studioAdapter.test.ts::studioAdapter.ts type union is wasm | mock (no http or pyodide)` — currently failing: type still includes `"http" | "pyodide"`
- `createStudioAdapter` has no `http` or `pyodide` branches → `studioAdapter.test.ts::createStudioAdapter has no http or pyodide branches` — currently failing: branches and imports remain
- resolution never returns http/pyodide → `studioAdapter.test.ts::resolveStudioAdapterKind never returns http or pyodide for any env` — currently failing: returns `"pyodide"` / `"http"` for default envs
- dev build resolves to wasm → `studioWiring.test.ts::dev build with API base URL still resolves to wasm kind` — currently failing: returns `"http"`
- prod build resolves to wasm → `studioWiring.test.ts::prod/demo build resolves to wasm kind (not pyodide)` — currently failing: returns `"pyodide"`
- `createStudioAdapter` dev default → `studioWiring.test.ts::createStudioAdapter builds WasmAdapter for dev default kind` — currently failing: builds `HttpAdapter`
- `createStudioAdapter` prod default → `studioWiring.test.ts::createStudioAdapter builds WasmAdapter for prod default kind` — currently failing: builds `PyodideAdapter`
- default path is WasmAdapter → `studioWiring.test.ts::studioAdapter default (no explicit mock) is WasmAdapter not MockAdapter` — currently failing: builds Http/Pyodide
- studioAdapter module WASM-only imports → `studioWiring.test.ts::studioAdapter module wires WasmAdapter only (no http/pyodide imports)` — currently failing: http/pyodide imports present
- footer copy WASM-only → `studioFooterEnv.test.ts::studioFooterCopy has no http or pyodide branches` — currently failing: http/pyodide branches in `studioFooterCopy`
- local defaults WASM worker/pkg → `studioFooterEnv.test.ts::resolveLocalStudioDefaults exposes WASM worker + pkg URLs (not pyodide wheel)` — currently failing: pyodide worker + `/wheels/` wheel
- createStudioAdapter wasm defaults → `studioFooterEnv.test.ts::createStudioAdapter wasm defaults use local WASM worker + pkg URLs` — currently failing: builds PyodideAdapter
- env/docs WASM defaults → `studioFooterEnv.test.ts::documents WASM defaults via .env.example or studioAdapter contract constants` — currently failing: pyodide env vars in `.env.example`
- mock-only explicit override; wasm default adapter → `studioFooterEnv.test.ts::createStudioAdapter returns MockAdapter only for mock kind / env` — currently failing: prod default builds PyodideAdapter
- default readiness wasm → `studioFooterEnv.test.ts::default readiness path resolves to wasm and does not silently fall back to mock` — currently failing: kind is `"pyodide"`, adapter is PyodideAdapter
- smoke checklist WASM narrative → `studioWiring.test.ts::ships a dedicated smoke checklist under .team/qa/ or mockup README` — currently failing: T-057-smoke.md still documents Http/Pyodide

## Not covered by tests

- `web/vite.config.ts` does not serve `/packaging/pyodide/` or `/wheels/` middleware — covered by other T-125 shards; verify by config inspection
- `web/package.json` default `studio` script runs WASM; `studio:http` / `studio:pyodide` absent — covered by other shards
- `scripts/studio.sh` has no `--http` / `--pyodide` flags — covered by other shards
- Full `cd web && npm test` pass — verifier owns after all shards land
