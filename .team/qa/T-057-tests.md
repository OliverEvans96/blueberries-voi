# T-057 — acceptance criteria → tests

## Coverage of acceptance criteria

- Studio/dev build default engine is **HttpAdapter** (local API) when configured
  → `web/src/engine/studioWiring.test.ts::T-057 studio adapter selection (dev=HTTP, prod=Pyodide) > dev build with API base URL resolves to HttpAdapter kind` — currently failing: stub returns `mock`
  → `… > createStudioAdapter builds HttpAdapter for dev/http kind` — currently failing: stub returns `MockAdapter`

- Prod/demo build default engine is **PyodideAdapter**
  → `… > prod/demo build resolves to PyodideAdapter kind` — currently failing: stub returns `http`
  → `… > createStudioAdapter builds PyodideAdapter for prod/pyodide kind` — currently failing: stub returns `MockAdapter`

- Controls that previously called mock `toViewModel` now go through projector + adapter
  (`init` / `step` / `step_n` / `reset` / `act` as applicable)
  → `… > main.ts constructs the studio adapter via createStudioAdapter (not bare MockAdapter default)` — currently failing: `main.ts` still uses `new MockAdapter()`
  → `… > main.ts imports HttpAdapter and PyodideAdapter selection (or studioAdapter helper)` — currently failing: only `MockAdapter` import
  → `… > Advance / Reset / bootstrap go through adapter.step / reset / init + projector` — currently **passing** (chrome already uses adapter + projector; still gated by default MockAdapter selection)

- Economics sliders call `projector.setEconomics` only (no network/worker)
  → `… > economics sliders call projector.setEconomics only (no adapter / network)` — currently **passing** (handler already local)
  → `… > ViewModelProjector.setEconomics does not require an EngineAdapter` — currently **passing**

- Default path no longer uses fake JS physics generator for Advance when a real adapter is
  selected (Mock may remain as an explicit debug option)
  → `… > studioAdapter default (no explicit mock) is not MockAdapter` — currently failing: stub always returns `MockAdapter`
  → `… > resolveStudioAdapterKind never silently defaults to mock without override` — currently failing: stub returns `mock` for configured dev
  → `… > studioAdapter module does not import generate.ts day-loop helpers for defaults` — currently failing: missing `httpAdapter` / `pyodideAdapter` imports
  → `… > explicit VITE_ENGINE_ADAPTER=mock keeps Mock as a debug option` — currently failing: stub inverts override to `http`
  → `… > createStudioAdapter builds MockAdapter only when kind is mock` — currently **passing** (stub returns Mock for all kinds)

- Manual or automated smoke checklist recorded under `.team/qa/` or mockup README
  → `… > ships a dedicated smoke checklist under .team/qa/ or mockup README` — currently failing: no `T-057-smoke.md` / `web/README.md`

## Not covered by tests

- Exact Vite env variable documentation prose beyond the pinned keys in
  `StudioEnv` / open question — because the spec leaves naming to the implementer;
  verify by reading `.team/qa/T-057-smoke.md` or `web/README.md` after implement.
- End-to-end browser click-through against a live ASGI server / Pyodide wheel —
  because RED suite uses unit + source contracts; verify manually via the smoke
  checklist once adapters are selected.
