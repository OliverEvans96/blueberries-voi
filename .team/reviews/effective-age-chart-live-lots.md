# Review: effective-age-chart-live-lots

STATUS: APPROVED  
ROUND: 1  
BRANCH: `fix/effective-age-chart-live-lots` (uncommitted working tree)  
SCOPE: `web/src/engine/projector.ts`, `web/src/engine/projector.test.ts`

## Blocking

_None._

## Verdict summary

`asDay(day, liveLotsFallback)` correctly maps HTTP/Pyodide DayDelta shapes (no
`day.lots`) onto `history[].lots` via `delta.live_lots`, while non-empty
`day.lots` (mock) still wins. That matches ADR-aligned ground-truth cohort τ
for `#chart-history` / `renderHistory()`.

## Checklist

### 1. Fallback correctness (empty vs missing; mock wins)

- Missing `day.lots` (`undefined` / absent) → `liveLotsFallback ?? []`. Correct.
- Empty `day.lots` (`[]`) treated as no snapshot → same fallback. Matches stated
  intent; reasonable for the wire (Python never sends an empty `lots` key).
- Non-empty `day.lots` preferred over `live_lots`. Correct for mock.

### 2. Crash paths / `applySnapshot`

- **`applyDelta` path:** safe after this change; `asDay` always yields `lots: Lot[]`.
- **`applySnapshot` still throws** if `snapshot.history` entries omit `lots`
  (`d.lots.map(...)` at `projector.ts` ~230). EngineSession stores the same
  minimal day dicts (no `lots`) in `_history`, and `_snapshot()` can expose them.
- **Studio today:** `applySnapshot` only on `init` / `reset`, both clear history →
  empty array → no throw on the live path this fix targets.
- **Do not apply the same `live_lots` fallback to every history day** on
  Snapshot hydrate: `snapshot.live_lots` is *current* end-of-day inventory only;
  painting it onto past days would corrupt the chart. Harden with
  `(d.lots ?? []).map(...)` / `asDay(d)` (no live fallback) if you want
  defense-in-depth; reconstructing per-day cohorts on Snapshot needs a Python
  contract change.

**Before commit:** same `live_lots` fallback on `applySnapshot` is **not**
required (and would be wrong). Optional null-safe `lots` default is a nit /
follow-up.

### 3. Test coverage

- New test covers HTTP-shaped delta: day without `lots` + `live_lots` →
  `history[0].lots`. Adequate for the bug.
- Gaps (non-blocking): no assert that differing non-empty `day.lots` beats
  `live_lots`; no assert that `lots: []` falls back.

### 4. Types / Lot import / ADR comment

- `Lot` import from `../types` is correct; `readonly Lot[] | undefined` is fine.
- Comment accurately describes EngineSession / day_driver minimal day +
  `DayDelta.live_lots`. Citing “ADR 0100” for the omit-`lots` detail is slightly
  loose (0100 is the export split; omission is day_driver implementation; 0100
  SUPERSEDED BY 0106) — nit only. Do not switch the chart to belief ages.

### 5. Security

N/A (presentation projector only).

## Non-blocking

- [web/src/engine/projector.ts:228-231] `applySnapshot` assumes `d.lots` exists;
  use `(d.lots ?? []).map(...)` (or `asDay(d)`) to avoid a latent throw if a
  non-empty lotsless `Snapshot.history` ever arrives. Do **not** fill from
  `snapshot.live_lots`.
- [web/src/engine/projector.test.ts] Optional: assert mock `day.lots` wins when
  `live_lots` differs; optional: empty `lots: []` → fallback.
- Comment: prefer “EngineSession / day_driver minimal day” over implying ADR
  0100 text mandates omitting `lots`.
