STATUS: PASS

## Commands run

- `cd web && npm install` → exit 0, 123 packages audited, 0 vulnerabilities
- `cd web && npm test` → exit 0, 2 files / 13 tests passed (vitest 3.2.7)
- `cd web && npx tsc --noEmit` → exit 0, no type errors

Note: `git merge team/T-054/qa` was blocked by host hook; acceptance criteria were read from `team/T-054/qa` tip (`.team/specs/T-054.md`) while verifying implement tip `21783148c737d62ddf5dcbd40dfe855cf844e491`. AGENTS.md Python gates (ruff/mypy/pytest) were not the primary gate for this web-only ticket; user-requested web commands were run.

## Acceptance criteria

- [x] `ViewModelProjector` applies Snapshot and DayDelta into the existing `ViewModel` shape used by D3 charts — verified by `npm test` (`projector.test.ts` applySnapshot / applyDelta suites, 13/13 green)
- [x] `setEconomics` updates PnL / ghost locally **without** calling any engine adapter method — verified by `npm test` (`setEconomics (local reproject)` spy asserts)
- [x] `MockAdapter` implements `EngineAdapter` and returns Snapshot/DayDelta (not a full ViewModel from `step`) — verified by `npm test` (`mockAdapter.daydelta.test.ts`)
- [x] Heatmap density is computed in JS from flat belief marginals × lot counts — verified by `npm test` (`densityFromFlatBelief` suite)
- [x] Unit tests cover projector apply + economics-local path — verified by `npm test` (13 passed)
- [x] Fake physics may remain inside MockAdapter until T-057 — verified by observation: `web/src/mock/generate.ts` still present; not prohibited by tests

## Incomplete

- None
