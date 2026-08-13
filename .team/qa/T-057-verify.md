STATUS: PASS

## Commands run
- `cd web && npm install` → exit 0, 123 packages audited, 0 vulnerabilities
- `cd web && npm test` → exit 0, 5 files / 54 tests passed (incl. `studioWiring.test.ts`)
- `cd web && npx tsc --noEmit` → exit 0, clean typecheck

## Acceptance criteria
- [x] Studio/dev build default engine is **HttpAdapter** (local API) when configured — verified by `npm test` (`resolveStudioAdapterKind(DEV_ENV)` → `"http"`; `createStudioAdapter` → `HttpAdapter`)
- [x] Prod/demo build default engine is **PyodideAdapter** — verified by `npm test` (`resolveStudioAdapterKind(PROD_ENV)` → `"pyodide"`; `createStudioAdapter` → `PyodideAdapter`)
- [x] Controls that previously called mock `toViewModel` now go through projector + adapter (`init`/`step`/`reset` as applicable) — verified by `npm test` (main.ts source assertions for `adapter.init` / `step` / `reset` + projector; no bare `new MockAdapter()` default)
- [x] Economics sliders call `projector.setEconomics` only (no network/worker) — verified by `npm test` (slider handler body + `ViewModelProjector.setEconomics` unit check)
- [x] Default path no longer uses fake JS physics generator for Advance when a real adapter is selected (Mock may remain as explicit debug option) — verified by `npm test` (no `generate` day-loop import on Advance path; `VITE_ENGINE_ADAPTER=mock` still allowed; default createStudioAdapter not MockAdapter)
- [x] Manual or automated smoke checklist recorded under `.team/qa/` or mockup README — verified by presence of `.team/qa/T-057-smoke.md` (asserted in tests; file observed on disk)

## Incomplete
- (none)
