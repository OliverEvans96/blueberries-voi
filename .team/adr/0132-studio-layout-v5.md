# 0132. Studio cockpit layout v5 — center Today, Events column, Secondary chrome

STATUS: PROPOSED
DATE: 2026-08-17

## Context

ADR [0129](../adr/0129-studio-cockpit-redesign.md) established the Cockpit Grid with a
dedicated Run sidebar spanning Economics and tuning rows. T-127 layout v4 fixed masonry
whitespace by letting the sidebar span two row tracks, but user review found:

1. **Tetris gaps** — Economics and Events still fought the Run column for row height.
2. **Duplicated obs UX** — DecisionRail obs chips overlapped tuning-dock Observation section.
3. **Buried metrics** — age-comp and controller orders lived in tuning plots while Today showed
   low-value sales/stockout sparklines.
4. **Split tradeoff** — curve and histogram side-by-side consumed scarce sidebar width.

Round 3 feedback (T-130) finalizes a **3-column** grid: Economics | Today | Events, with
Secondary absorbing obs/truth/tradeoff chrome and OperatorBar.

## Decision

We will adopt **layout v5**:

1. **Grid** — three columns: charts (2 cols) + Events; middle row Economics + Today; bottom
   row tuning dock (2 cols). Events column spans all three rows on the right.
2. **Retire Run sidebar** — remove `DecisionRail` from the shell; mount `SecondaryChrome`
   (obs presets, truth toggle, Curve|Histogram tab) between histogram and OperatorBar.
3. **Today pane** — show inventory vs base-stock, controller order bars, and on-hand age-comp;
   keep `#chart-sales` / `#chart-stockout` in hidden hosts for hover-link wiring only.
4. **Tradeoff reactivity** — tab toggle shows one chart at a time; `useEffect` re-renders on
   `orderQty` and forecast updates (fixes stale ref rendering from T-127).
5. **Chart polish** — controller orders as bars; PnL lines without dots; histogram single-color
   aggregate belief bars.
6. **Tuning** — demand chart colocated with demand sliders; 1/σ label; styled α/ρ pad;
   rollout default.

## Alternatives considered

- **Keep DecisionRail sidebar** — rejected: duplicates obs controls and preserves the row-height
  mismatch that produced 300–400px dead space under Economics/Events.
- **Stack tradeoff curve + histogram vertically in sidebar** — rejected: still too tall; tab
  toggle preserves both views without doubling vertical budget.
- **Remove hidden sales/stockout hosts** — rejected: `attachLinkedHover` and stockout regression
  tests still reference those chart ids; hiding is cheaper than rewiring hover graph.

## Consequences

- **Easier** — single obs control surface; Today shows actionable controller metrics; Events log
  readable at full column height; e2e and vitest can target stable `data-obs` chips in
  SecondaryChrome.
- **Harder** — `studioLogic.ts` mount graph changes; DecisionRail tests migrate to
  SecondaryChrome; layout regressions require updating both `cockpitGrid.css` areas and
  `StudioLayout.test.ts`.
- **Locked in** — `#decision-rail-host` and `.cockpit-pane--run` are retired from the shell;
  reintroducing a fourth column requires a new ADR.
- **Cost** — one-time churn across layout CSS, studioLogic, e2e screenshots, and ~15 web test
  files; no Rust changes.
