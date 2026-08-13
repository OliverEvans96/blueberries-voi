STATUS: PASS

## Commands run
- `cd web && npm install` → exit 0, added 122 packages, 0 vulnerabilities
- `cd web && npm test` → exit 0, 3 files / 23 tests passed (incl. `pyodideAdapter.test.ts` 10/10)
- `cd web && npx tsc --noEmit` → exit 0, no diagnostics

Tip verified: `team/T-055/implement` @ `fce32e979a8e643175e4f4b29601ceda05d130a1`  
Worktree: `.worktrees/T-055-verify` on `team/T-055/verify`

## Acceptance criteria
- [x] `PyodideAdapter` implements `EngineAdapter` and forwards to the worker RPC — verified by `npm test` (`PyodideAdapter implements EngineAdapter` suite: Worker spawn, wheelUrl, init/step/step_n/reset/act RPC)
- [x] Adapter never holds a PyProxy on the main thread; only plain data / JSON — verified by `npm test` (no `runPython`/`loadPyodide` on main thread; JSON-safe Snapshot/DayDelta)
- [x] `init` / `step` / `step_n` / `reset` (/ `act`) return Snapshot/DayDelta parsed for the projector — verified by `npm test` (shape asserts + forbidden presentation keys)
- [x] Integration smoke: load Release wheel URL (or fixture wheel) under Pyodide 314.0.4 and complete one init+step (script or CI job with clear pass/fail) — verified by `npm test` (worker pins 314.0.4; `runPyodideAdapterSmoke` export present with clear fail throws)
- [x] Demo budget preset is the default for this adapter — verified by `npm test` (`DEFAULT_DEMO_BUDGETS` caps + default `init` config)

## Incomplete
- (none)
