# T-127 round 2 — visual QA

**Verdict:** PASS

**Branch:** `team/T-127/integrate-implement` @ `ba1dc9a` (visual-qa branch merged in)

**Scope:** Frontend-only (`web/`). Cockpit redesign: always-visible Primary
(freshness×time heatmap + sales/demand/stockout + waste) and Secondary
(stacked freshness histogram) panes, Economics pane P&L consolidation,
observation-scenario-aware Events pane, tuning dock re-navigation, tradeoff
forecast charts colocated with the order control.

## What was checked

Ran a Playwright suite (`web/tests/studio-visual-qa.spec.ts`, 9 tests) plus
the existing smoke test against a real dev server (chromium), driving the
simulator forward several days so charts have data, then asserting on DOM
structure, ARIA state, and rendered SVG element counts:

1. No "Play" tab; Primary/Secondary panes always present.
2. Primary pane 3-chart stack renders; truth-overlay toggle adds/removes
   per-lot dots on the freshness×time heatmap.
3. Secondary pane is freshness-histogram-only; truth bars appear/disappear
   with the truth toggle.
4. Exactly one order-quantity control and one advance button (no duplicate
   `PlayChrome` controls).
5. Tradeoff dual-line + joint-histogram charts render with real data.
6. Economics pane has no dead P&L sparkline/series hosts and shows a
   cumulative P&L chart.
7. Events pane content changes correctly per observation scenario
   (P0/P1/F1/F1s/F2a/F2).
8. Tuning dock: every tab reveals its own section content, including the
   2D alpha/rho autopilot pad.
9. General polish: layout holds at 1440px and 1024px viewports, **zero
   console errors** across a full scenario-switching + interaction pass.

Also ran the full `vitest` suite (52 files / 378 tests) and `npm run build`
(`tsc && vite build`) — all clean.

## Bugs found and fixed in this pass

- **`removeChild` crash on scenario switch:** `#chart-spoil` is shared
  between a React root (`ChartUnavailable` placeholder, shown when waste is
  not observed at the current rung) and a raw D3 renderer
  (`renderWasteBars`). Unmounting the React root with `.render(null)` is
  asynchronous; the very next line synchronously wiped the same container
  with D3, so React's later commit tried to remove a node D3 had already
  detached, throwing `NotFoundError` and logging a React error-boundary
  warning on every P0/P1 ⇄ other-scenario transition. Fixed by wrapping the
  unmount in `flushSync` so it commits before the D3 wipe runs
  (`web/src/react/studioLogic.ts`).
- **Grammar:** events lot breakdown always said "N units" even for N=1.
  Fixed to singularize (`web/src/react/EventsPane.tsx`), and updated the
  matching unit test.

## Notes / follow-ups

- Python/Rust CI gates are unaffected (no changes outside `web/`); see
  `.team/qa/T-127.md` for the existing PASS on the Python side.
- Backend follow-ups already tracked in `.team/backlog.md` under
  "T-127 studio cockpit follow-ups" (mocked delivery temperature trace,
  base-stock autopilot policy, configurable delivery/order weekdays,
  pricing-slider colocation).
