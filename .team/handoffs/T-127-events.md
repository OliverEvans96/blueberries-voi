# T-127 events implement handoff (wave 1, round 2)

**Branch:** `team/T-127/events-implement`  
**Worktree:** `.worktrees/T-127-events-implement`

## What changed

### `web/src/react/EventsPane.tsx`
- Day cards sorted **latest-first** (`day` descending) before render.
- `sales_by` / `waste_by` breakdowns zipped with `lot_ids` → e.g. `Lot 101: 4 units, Lot 102: 1 units`. When `lot_ids` is absent, breakdown text is omitted (totals only).
- **Pack date** row shown only when `maskFor(obs_scenario).pack_date` (F2a).
- **Age at receipt** row shown only when `maskFor(obs_scenario).age_at_receipt` (F2, not F2a).
- Delivery days (`arrivals > 0`) mount an illustrative temp-history mini chart via ref callback (DecisionRail tradeoff pattern).
- `<hr class="events-day-divider">` between day cards (not before the first).

### `web/src/charts/deliveryTempMock.ts` (new)
Frontend-only placeholder — no WASM wire field.

| Export | Signature |
|--------|-----------|
| `seedForDeliveryTemp` | `(day: number, lotId: number) => number` |
| `generateDeliveryTempHistory` | `(day: number, lotId: number) => DeliveryTempPoint[]` |
| `renderDeliveryTempHistorySvg` | `(svg: SVGSVGElement, data: DeliveryTempPoint[]) => void` |
| `renderDeliveryTempHistory` | `(host: HTMLElement, day: number, lotId: number) => void` |

`DeliveryTempPoint = { t: number; temp: number }` with `t ∈ [0,1]`, `temp` bounded ~0.5–6 °C. Seeded mulberry32 on `(day, lotId)`. D3 axis-less line + dashed 2 °C baseline.

Chart seed on delivery card: `day` + first `lot_ids[0]` (or `0` when lots unobserved).

### `web/src/styles/eventsPane.css`
Divider, breakdown/temp caption typography, temp chart host sizing.

### Tests
- `web/src/charts/deliveryTempMock.test.ts` — seed stability, bounds, SVG render.
- `web/src/react/EventsPane.test.ts` — latest-first order, lot labels, F2/F2a mask rows, temp chart, P0 breakdown hidden.

## Masking accuracy (obs.rs cross-check)

Verified against `crates/voi_core/src/obs.rs`:

| Scenario | `mask_for` (lines) | UI rows |
|----------|-------------------|---------|
| F2a | `pack_date: true`; **no** `age_at_receipt`, `lot_ids_live`, maps (96–101) | Pack date only; no age row |
| F2 | `age_at_receipt: true`, maps + `lot_ids_live`; **no** `pack_date` (103–111) | Age at receipt + lot breakdowns; no pack date row |

**Pre-existing mislabel bugs:** none found in prior `EventsPane.tsx` copy (those fields were not rendered). Fix applied proactively: mask-gated rows use `maskFor(vm.config.obs_scenario)` so F2a cannot surface an age-at-receipt row and F2 cannot surface pack date.

`obsMask.ts` already matches Rust (F2a test at obs.rs:218–223).

## Integrate / visual-qa checklist

1. Switch obs ladder P0 → F2a → F2 on a run with deliveries; confirm Events pane rows match table above without Reset.
2. Confirm day cards appear newest at top.
3. Confirm temp chart appears only on delivery days, caption reads `temp. history (illustrative)`.
4. F1/F1s: breakdown labels only when `lot_ids` present in masked wire.

## Verification (this worktree)

```bash
cd web && npm run test   # 346 passed
cd web && npm run build  # tsc + vite build OK
```
