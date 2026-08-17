# T-127 secondary implement handoff — stacked freshness histogram

## Exported API

```typescript
// web/src/charts/freshnessHistogram.ts

export type FreshnessLotSegment = {
  lot_index: number;
  lot_id: number;
  masses: number[]; // length K, belief mass per freshness bin
};

export type FreshnessHistogramData = {
  f_edges: number[]; // length K+1
  segments: FreshnessLotSegment[];
  truth_lots: Lot[];
  highlight_lot_id: number | null; // newest delivery (max lot_id with n > 0)
};

export function freshnessHistogramDataFromFlat(
  flat: FlatBelief,
  truthLots?: readonly Lot[],
): FreshnessHistogramData;

export function renderFreshnessHistogram(
  container: HTMLElement,
  data: FreshnessHistogramData,
  showTruth: boolean,
  height?: number, // default 260
): void;
```

## Container ids replaced

Integrate agent should mount **one** chart in the Secondary pane, replacing both:

| Old host | Old renderer | Status |
|----------|--------------|--------|
| `#chart-belief-lg` | `renderBeliefAgeCount` | superseded |
| `#chart-belief-age-marginal` | `renderBeliefAgeMarginal` | superseded |

Confirmed in `web/src/react/StudioLayout.tsx` (`D3_CHART_IDS` + Secondary pane hosts).

Suggested wiring in `studioLogic.ts` `renderCockpitBelief()`:

```typescript
import {
  freshnessHistogramDataFromFlat,
  renderFreshnessHistogram,
} from "../charts/freshnessHistogram";

const flat = vm.belief_history.at(-1)?.flatBelief;
if (flat) {
  const data = freshnessHistogramDataFromFlat(flat, vm.live_lots);
  renderFreshnessHistogram(els.beliefLg, data, showTruth, 260);
  els.beliefAgeMarginal.replaceChildren(); // or hide host / remove from layout
}
```

`showTruth` follows existing `truthLots(showTruth, vm.live_lots)` convention: pass the boolean; truth bars render only when `true`, using `data.truth_lots` (populate from `vm.live_lots` in the builder call).

## Data-shape assumptions

| Field | Source | Notes |
|-------|--------|-------|
| Belief masses | `FlatBelief` via `vm.belief_history.at(-1)` | `mass[l][k] = lot_counts[l] * f_marginals[l*K+k]` |
| Bin edges | `centersToEdges(f_grid)` from projector | Reuses existing projector helper |
| Truth overlay | `Lot[]` with `lot_id`, `n`, `mean_f` | Height ∝ `n`; x at `mean_f` |
| Newest lot highlight | max `lot_id` among truth lots with `n > 0` | Stacked **underneath** (first d3.stack key); class `freshness-stack-series--highlight` |
| Belief lot ↔ truth id | positional index in `truthLots[l]` | Falls back to `lot_id = l` when truth array shorter than `L` |

**No changes to `types.ts` or `projector.ts` required.** Integrate agent only needs latest `belief_history` entry + `live_lots`.

### Optional layout follow-up

- Secondary pane may collapse to a single `#chart-belief-lg` host (height ~260) and drop or hide `#chart-belief-age-marginal` caption/host — **all 14 `D3ChartHost` ids must remain in DOM** per AC-layout; empty/hidden marginal host is acceptable.
- CSS tokens used: `--color-freshness-highlight` (fallback `#c9a227`), `--color-truth-bar` (fallback `#1a1a1a`).

## Tests

`web/src/charts/freshnessHistogram.test.ts` — jsdom unit tests for data builder, stacked segments, highlight-underneath ordering, truth toggle gating, truth bar heights.
