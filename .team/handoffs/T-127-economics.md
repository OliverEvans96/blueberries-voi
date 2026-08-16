# T-127 economics-implement handoff (wave 1, round 2)

Branch: `team/T-127/economics-implement`  
Scope: consolidated cumulative P&L chart inside `EconomicsPane`.

## (a) Chart mount export

**File:** `web/src/react/EconomicsPane.tsx`

```ts
export function mountEconomicsPnLChart(
  container: HTMLElement,
  series: DayPnL[],
  height = 160,
): void
```

- Delegates to `renderPnLTimeseries` from `web/src/charts/pnlTimeseries.ts`.
- Wired in JSX via ref callback on `#chart-pnl-economics`:

```tsx
ref={(node) => {
  if (node) mountEconomicsPnLChart(node, vm.pnl_series);
}}
```

- Container: `#chart-pnl-economics` (`data-testid="chart-pnl-economics"`), sibling caption
  “Cumulative revenue · cost · profit”.

## (b) Redundant chart mounts for integrate agent

The Economics pane now renders the same cumulative revenue / cost / profit series from
`vm.pnl_series`. These **legacy mounts** should be removed by the integrate agent once the
consolidated chart is confirmed in the shell:

| Id | DOM location | studioLogic wiring |
|----|--------------|-------------------|
| `chart-pnl-spark` | `StudioLayout.tsx` — Run impact strip, caption “Cumulative PnL” | `els.pnlSpark = document.querySelector("#chart-pnl-spark")`; `renderRunStripCharts()` → `renderPnLTimeseries(els.pnlSpark, vm.pnl_series, 118)` (~lines 180, 445) |
| `chart-pnl-series` | `StudioLayout.tsx` — tuning dock `.focus-plot[data-plot="plot-pnl"]` inside `<details class="ledger-expand">` | `els.pnlSeries = document.querySelector("#chart-pnl-series")`; `renderFocus()` when `plotVisible("plot-pnl")` → `renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 160)` (~lines 179, 521–523); also re-render on hover (~736) |

**Integrate cleanup checklist:**

1. Remove `#chart-pnl-spark` `D3ChartHost` (+ caption) from Run impact strip in `StudioLayout.tsx`.
2. Remove `#chart-pnl-series` `D3ChartHost` (+ `.focus-plot[data-plot="plot-pnl"]` block) from tuning dock in `StudioLayout.tsx`.
3. Drop `pnlSpark` / `pnlSeries` from `els` in `studioLogic.ts` and all `renderPnLTimeseries` calls targeting them.
4. Remove `chart-pnl-spark` / `chart-pnl-series` from `REQUIRED_CHART_IDS` in `StudioLayout.test.ts` (count drops 15 → 13 unless other charts added).
5. Optional CSS cleanup: `#chart-pnl-spark` rules in `web/src/styles.css`.

Do **not** remove `renderPnLTimeseries` / `pnlTimeseries.ts` — Economics pane still uses it.

## (c) Pricing slider wiring check

**Status: NOT wired to `#economics-pricing-host` (placeholder only).**

- `EconomicsPane.tsx` renders an empty `<div id="economics-pricing-host" />`.
- Pricing sliders (`p_sell`, `c_unit`, `c_waste`, `c_stockout`) remain in `controls.ts`:
  - `PRICE_SLIDERS` array (~lines 127–131)
  - HTML in `.controls-block[data-section="pricing"]` (~line 233)
  - Event listeners call `cb.onEconomicsChange` (~lines 378–386)
- Those controls mount into `#section-controls` via `studioLogic.ts` (`els.sectionControls`) — **not**
  reparented into `#economics-pricing-host`.
- **Ping tuning-dock agent:** move or clone pricing sliders into `#economics-pricing-host` (or portal
  from controls) while preserving `onEconomicsChange` / `setEconomics` instant-local path.

## Tests / build

- `web/src/react/EconomicsPane.test.tsx` — summary, chart SVG, `mountEconomicsPnLChart` export.
- Existing `web/src/charts/pnlTimeseries.test.ts` unchanged (chart logic already covered).
