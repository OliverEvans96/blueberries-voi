# T-074 RED map — Studio footer, env defaults, live-adapter errors (ADR 0108)

## Coverage of acceptance criteria

- Studio footer no longer says **“Fake data studio”** when adapter is `http` or
  `pyodide`  
  → `web/src/engine/studioFooterEnv.test.ts::T-074 studio footer for live adapters > studioFooterCopy(http)…` — currently failing: `studioFooterCopy` is not exported / not a function  
  → `… > studioFooterCopy(pyodide)…` — same  
  → `… > main.ts footer is driven by adapter kind…` — currently failing: footer hardcodes `Fake data studio · blueberries-voi`; no `studioFooterCopy` / equivalent

- Default / documented local env: localhost API base; local worker + local wheel
  (not only `github.com/oliver/...`)  
  → `… > resolveLocalStudioDefaults exposes localhost API base…` — currently failing: `resolveLocalStudioDefaults` not a function  
  → `… > resolveLocalStudioDefaults uses local worker + local wheel…` — same  
  → `… > createStudioAdapter pyodide defaults use local worker + local wheel URLs` — currently failing: default `wheelUrl` still embeds `github.com/oliver/`  
  → `… > documents local defaults via .env.example or studioAdapter contract constants` — currently failing: no `.env.example` and code default wheel still GitHub-only

- Adapter init/step failures surface to the user (non-silent)  
  → `… > reportStudioAdapterError writes a non-empty visible message on a target` — currently failing: `reportStudioAdapterError` not a function  
  → `… > main.ts catches adapter init/step failures…` — currently failing: no `catch` / `reportStudioAdapterError` / `#studio-error` wiring on bootstrap/Advance

- `MockAdapter` only when `VITE_ENGINE_ADAPTER=mock`; no silent mock fallback  
  → `… > resolveStudioAdapterKind is mock only for explicit override` — **passing** (T-057 contract already holds)  
  → `… > createStudioAdapter returns MockAdapter only for mock kind / env` — **passing**  
  → `… > default readiness path does not silently fall back to mock` — **passing**

- Vitest covers footer/env selection behaviours  
  → Proven RED: `cd web && npm test -- --run src/engine/studioFooterEnv.test.ts` → **9 failed / 3 passed**

## Local env contract (qa note — ADR 0108 / T-074)

| Piece | Documented default |
|-------|--------------------|
| HTTP API base | `http://127.0.0.1:8000` (or `http://localhost:8000`) via `VITE_ENGINE_API_BASE_URL` / `resolveLocalStudioDefaults().apiBaseUrl` |
| Pyodide worker | `/packaging/pyodide/worker.js` (`VITE_PYODIDE_WORKER_URL`) |
| Local slim wheel | `/wheels/blueberries_voi-0.1.0-py3-none-any.whl` (`VITE_PYODIDE_WHEEL_URL`) |
| Footer | `studioFooterCopy(kind)` — live kinds must not claim fake/mock |
| Errors | `reportStudioAdapterError(message, target?)` + main.ts `catch` on init/step/reset |

## Not covered by tests

- Exact client-readable footer wording (implementer chooses; tests only forbid fake/mock claims for live kinds).
- Live HTTP/Pyodide smoke evidence file (T-075).
- Arrival-only filter (T-067–T-069) / ADR 0105–0106.
