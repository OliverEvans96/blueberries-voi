# T-116 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- Chart-stack order Units sold (`#chart-sales`) → **Missed sales**
  (`#chart-stockout`) → Lots (`#chart-history`) → Units spoiled (`#chart-spoil`);
  caption exactly `Missed sales`
  → `web/src/main.stockout.test.ts::Store chart-stack missed sales (T-116) > chart-stack order: Units sold, sales, Missed sales, stockout, Lots, history, Units spoiled, spoil`
  — currently failing: `.chart-stack` has no Missed sales / `#chart-stockout` (missed index `-1`)
  → `… > caption text is exactly "Missed sales"`
  — currently failing: no `chart-caption` with that exact text

- `renderMarginal(..., "stockout")` draws `.bar.bar--stockout` from
  `history[i].stockout`; bars grow **up** like sales (`y = yScale(v)`,
  `height = innerH - yScale(v)`); no `.axis-x` on stockout; spoilage still has
  `.axis-x`
  → `web/src/charts/marginals.stockout.test.ts::MarginalKind stockout (T-116) > exported MarginalKind includes "stockout"`
  — currently failing: `MarginalKind` is not exported and has no `"stockout"`
  → `…::renderMarginal stockout mapping and geometry (T-116) > kind stockout maps d.stockout (not waste_total as the stockout value)`
  — currently failing: no `kind === "stockout"`; values use `sales_total` / `waste_total` only
  → `… > stockout bar geometry is upward like sales (yScale(v) / innerH - y), not y=0 like spoilage`
  — currently failing: `.bar` join has no stockout / `d.stockout` branch
  → `… > no .axis-x for stockout; kind === "spoilage" still has x axis`
  — currently failing: no `kind === "stockout"` (spoilage `axis-x` already present)

- CSS `--missed` / `--missed-strong`; `.bar--stockout` / `.bar--stockout.bar--active`;
  store legend **Missed** chip `chip-missed` alongside Sales / Lots / Spoilage
  → `web/src/main.stockout.test.ts::Missed-sales CSS tokens (T-116) > defines --missed and --missed-strong`
  — currently failing: tokens absent from `styles.css`
  → `… > .bar--stockout uses --missed; active uses --missed-strong`
  — currently failing: no `.bar--stockout` rules
  → `… > defines .chip-missed`
  — currently failing: no `.chip-missed`
  → `…::Store chart-stack missed sales (T-116) > store legend includes chip-missed alongside Sales / Lots / Spoilage`
  — currently failing: legend has Sales / Lots / Spoilage only

- Shared y-domain `max(sales_total, stockout)` (+ ghost stockout); `renderStore`
  uses `marginalYMax` and the same `yMax` for sales and stockout
  → `web/src/charts/marginals.stockout.test.ts::MarginalKind stockout (T-116) > exports marginalYMax(history, ghost?)`
  — currently failing: no `export function marginalYMax`
  → `… > renderMarginal accepts optional yMax after ghost`
  — currently failing: signature ends at `ghost`; no `yMax?`
  → `…::renderMarginal stockout mapping and geometry (T-116) > sales and stockout use shared yMax when passed (Math.max(1, yMax))`
  — currently failing: `marginals.ts` has no `yMax`
  → `web/src/main.stockout.test.ts::… > renderStore shares marginalYMax / yMax for sales and stockout`
  — currently failing: `renderStore` calls `renderMarginal(els.sales, …, "sales", 72)` with no shared max / stockout call

- Ghost stockout `.bar-ghost` from `ghost.series[].stockout`, upward geometry;
  spoilage ghost from `series[].waste` unchanged
  → `web/src/charts/marginals.stockout.test.ts::… > stockout ghost uses p.stockout and upward geometry (not y=0 spoilage ghosts)`
  — currently failing: no stockout ghost branch (`p.stockout` / upward `innerH - y`)

- `applyHoverStyles` calls `setMarginalHover(els.stockout, day)`; `els.stockout` → `#chart-stockout`
  → `web/src/main.stockout.test.ts::… > els.stockout binds #chart-stockout`
  — currently failing: no `els.stockout` / `#chart-stockout` query
  → `… > applyHoverStyles calls setMarginalHover(els.stockout, day)`
  — currently failing: hover only sales + spoil (+ history)

- Demand **Sales vs demand** (`renderSalesDemand` / `#chart-sales-demand`) unchanged
  line/gap chart
  → `web/src/main.stockout.test.ts::… > Demand Sales vs demand / chart-sales-demand still a line chart module`
  — currently **passing** (regression guard)

## Not covered by tests

- D3 pixel proof that max stockout > max sales shortens sales bars — Node vitest
  has no jsdom; shared `marginalYMax` / `yMax` source contracts are the RED gate.
- `bar--active` / `day-hit--active` at runtime on hover — `setMarginalHover` is
  already style-only on `.bar` / `.day-hit`; wiring is the `els.stockout` source
  contract. Full DOM hover is implement / visual verify.
- No production edits under `src/blueberries_voi/`, `crates/`, WASM adapters;
  `package.json` / lockfile unchanged — process/diff check for review + verify,
  not a feature RED test.

## RED command

```bash
cd web && npx vitest run src/charts/marginals.stockout.test.ts src/main.stockout.test.ts
```

## RED evidence (qa worktree)

```
Test Files  2 failed (2)
Tests       17 failed | 1 passed (18)
```

Failing for missing missed-sales / stockout behaviour (kind, yMax, stack
markup, CSS tokens, hover wiring), not import typos. The one pass is the Demand
Sales vs demand regression guard.
