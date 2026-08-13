# T-056 — acceptance criteria → tests

## Coverage of acceptance criteria

- `HttpAdapter` implements `EngineAdapter` against the T-049 route table
  → `web/src/engine/httpAdapter.test.ts::HttpAdapter implements EngineAdapter (T-049 routes) > exposes init / step / step_n / reset as EngineAdapter`
  → `… > init returns a Snapshot (seq, episode_day, flat belief)` — currently failing: stub returns `{}`
  → `… > step returns a DayDelta (day + drop_oldest)` — currently failing: stub returns `{}`
  → `… > step_n returns DayDelta[] (unwraps { deltas })` — currently failing: stub returns `[]`
  → `… > reset returns a Snapshot` — currently failing: stub returns `{}`
  → `… > HttpAdapter fetch contract …` (create / init / step / step_n / reset / dispose path tests) — currently failing: no `fetch` calls

- Uses `fetch` (or project HTTP helper) with JSON bodies; parses Snapshot/DayDelta
  → `web/src/engine/httpAdapter.test.ts::HttpAdapter fetch contract (paths + JSON bodies) > init POSTs /sessions/{id}/init with JSON { config, seed? }` — currently failing: no init call / Content-Type
  → `… > step POSTs … with { order_qty }` — currently failing: no step call
  → `… > step_n POSTs … with { orders }` — currently failing: no step_n call
  → `… > HttpAdapter Snapshot/DayDelta only … > init and step payloads omit economics / pnl / ghost / heatmap` — currently failing: empty stub payloads

- Session create on construct/`init`; delete/reset behaviour documented
  → `… > creates a session with POST /sessions (construct or init)` — currently failing: no create call
  → `… > reset POSTs /sessions/{id}/reset (keeps session)` — currently failing: no reset call
  → `… > dispose DELETEs /sessions/{id}` — currently failing: no DELETE
  → Lifecycle documented in `web/src/engine/httpAdapter.ts` JSDoc (create / reset / dispose)

- Contract test or mock-fetch test asserts request paths/bodies and that economics are not POSTed on `setEconomics` (economics stay in projector)
  → all `HttpAdapter fetch contract` path/body tests above — currently failing: missing fetch behaviour
  → `… > Economics stay in projector … > ViewModelProjector.setEconomics does not trigger HttpAdapter fetch` — currently failing: init never hits network (`calls.length === 0`); after implement, asserts no economics POST and no `adapter.setEconomics`

- Points at local base URL configurable via constructor / env
  → `… > HttpAdapter base URL … > uses constructor baseUrl as the request origin` — currently failing: no requests
  → `… > reads VITE_ENGINE_API_BASE_URL when baseUrl omitted` — currently failing: no requests / env not read

## Not covered by tests

- Live HTTP against a running uvicorn/ASGI process — because this ticket locks the
  adapter contract with mock-fetch; verify end-to-end manually or in T-057 studio wiring
  with `uv run` API + Vite proxy.
- Optional `act` route body mapping — EngineAdapter.act is optional; T-056 AC list
  names init/step/step_n/reset. Implementer may add `act` for parity; not required for
  RED green of listed criteria.
- PyodideAdapter — T-055 (out of scope).
