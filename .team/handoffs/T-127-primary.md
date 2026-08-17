# T-127 Primary implement handoff (wave 1, round 2)

Branch: `team/T-127/primary-implement`

## `beliefFreshnessTime.ts` — replace `#chart-history` (+ optionally retire belief heatmaps in Primary)

### Exported API

```ts
// web/src/charts/beliefFreshnessTime.ts

export type BeliefFreshnessTimeDims = {
  width: number;
  height: number;
  margin: { top: number; right: number; bottom: number; left: number };
};

export const BELIEF_DAY_SUBSTEPS = 4;  // sub-day interpolation (display only)
export const BELIEF_F_SUBSTEPS = 4;    // finer freshness bins (display only)

export function dayDomain(history: Day[]): [number, number];

export function buildBeliefFreshnessHeatmap(
  series: BeliefFreshnessDay[],
  daySubsteps?: number,
  fSubsteps?: number,
): HeatCell[];

export function setBeliefFreshnessTimeHover(
  container: HTMLElement,
  hoveredDay: HoverDay,
): void;

export function renderBeliefFreshnessTime(
  container: HTMLElement,
  history: Day[],
  beliefHistory: BeliefHistoryDay[],
  showTruth: boolean,
  dims?: Partial<BeliefFreshnessTimeDims>,
): void;
```

- **Mount target:** `#chart-history` in `StudioLayout.tsx` (Primary pane). This replaces `renderHistory` from `history.ts`.
- **Also supersedes (integrate may remove from Primary / Secondary):** the freshness×count heatmaps currently on `#chart-belief-lg` and `#chart-belief-age-marginal` are *not* duplicated here — Secondary keeps its own hosts; Primary is now freshness×**time** only.
- **Data:** `vm.history` (per-day `lots` for truth overlay) + `vm.belief_history` (rolling `FlatBelief` per day).
- **Truth toggle:** pass `showTruth` boolean (same convention as `truthLots(showTruth, …)` / `DecisionRail`). When `false`, dots and connecting lines are omitted.
- **Hover link:** call `setBeliefFreshnessTimeHover(container, day)` from `applyHoverStyles` alongside other linked charts. SVG uses `chart-svg` + `chart-root` + `.day-col` / `.hover-rule` (same contract as `history.ts` / `marginals.ts`).

## `projector.ts` — presentation helpers

```ts
export type BeliefFreshnessDay = {
  day: number;
  f_edges: number[];
  marginal: number[]; // length K, Σ_l lot_counts[l] × f_marginals[l,k]
};

export function beliefFreshnessSeries(
  beliefHistory: BeliefHistoryDay[],
): BeliefFreshnessDay[];
```

- **No `ViewModel` shape change.** Integrate can call `beliefFreshnessSeries(vm.belief_history)` or pass `vm.belief_history` directly to `renderBeliefFreshnessTime`.
- Existing `fMarginalFromFlat` / `centersToEdges` unchanged.

## `salesDemand.ts` — stockout red shading

### New / changed exports

```ts
export function salesDemandX(days: readonly number[], innerW: number, day: number): number;
export function setSalesDemandHover(container: HTMLElement, hoveredDay: HoverDay): void;
export function renderSalesDemand(container: HTMLElement, history: Day[], height?: number): void;
```

- **Stockout gap:** `d3.area` path `.sales-demand-gap` with red fill `rgba(196, 58, 58, 0.22)` between demand and sales wherever `demand > sales_total`.
- **Hover link:** `chart-svg` + `chart-root` + `.day-hit` / `.hover-rule`. Wire `setSalesDemandHover(els.salesDemand, day)` in `applyHoverStyles`.
- **Mount:** currently `#chart-sales-demand` in tuning dock; integrate may relocate into Primary stack.

## `marginals.ts` — waste bars for Primary stack

### New exports

```ts
export function wasteBarYMax(history: Day[]): number;
export function renderWasteBars(
  container: HTMLElement,
  history: Day[],
  height?: number,
  yMax?: number,
): void;
export function setWasteBarsHover(container: HTMLElement, hoveredDay: HoverDay): void;
```

- Uses `salesDemandX` for bar centers (same day-band convention as `renderSalesDemand`).
- `chart-svg` + `chart-root` + `.bar--spoilage` + `.day-hit` / `.hover-rule`.
- **Suggested mount:** new host in Primary stack (e.g. reuse `#chart-spoil` after moving out of store tab, or add a dedicated id — integrate decides).
- `setWasteBarsHover` delegates to `setMarginalHover` (identical DOM contract).

## Integrate wiring checklist

1. Replace `renderHistory(els.history, …)` with `renderBeliefFreshnessTime(els.history, vm.history, vm.belief_history, showTruth, { height: 220 })`.
2. Add `setBeliefFreshnessTimeHover(els.history, day)` to `applyHoverStyles`.
3. Optionally stack `renderSalesDemand` + `renderWasteBars` under the heatmap in Primary; register `setSalesDemandHover` / `setWasteBarsHover`.
4. Ensure `#linked-charts` (or Primary sub-region) is the `attachLinkedHover` root if charts move.
5. Update captions: Primary is now “Freshness × time” not “Lots · day × freshness”.
6. Delete `history.ts` mount only after integrate confirms; file left untouched this wave.

## Tests added

- `web/src/charts/beliefFreshnessTime.test.ts`
- `web/src/charts/salesDemand.test.ts`
- `web/src/charts/marginals.waste.test.ts`
- `web/src/engine/projector.test.ts` — `beliefFreshnessSeries` case
