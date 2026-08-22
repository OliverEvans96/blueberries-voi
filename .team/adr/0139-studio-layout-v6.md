# 0139. Studio cockpit layout v6 — metrics | belief | sidebar

STATUS: PROPOSED
DATE: 2026-08-22

## Context

ADR [0132](../adr/0132-studio-layout-v5.md) established layout v5: Economics | Today | Events
with SecondaryChrome hosting observation toggles and tradeoff mini-charts. User review (T-148)
found:

1. **Header noise** — hero brand, lede, insight strip, and chapter tabs competed with the cockpit.
2. **Metric scatter** — P&L, inventory, orders, and impact totals were split across Economics,
   Today, and tuning plots.
3. **Observation duplication** — SecondaryChrome obs controls overlapped tuning Observation tab.
4. **Tradeoff placement** — curve/histogram consumed Secondary vertical budget; better as reference
   material tied to controller teaching.
5. **Events log** — protection-interval fetch was hard to scan; a fixed 5-day window with
   Delivered | Sold | Spoiled columns is clearer.

## Decision

We adopt **layout v6**:

1. **Header** — minimal `.title-bar`: app title + `#engine-status` only.
2. **Grid** — `metrics | belief | sidebar` + full-width tuning dock:
   `grid-template-areas: "metrics belief sidebar" / "tuning tuning tuning"`.
3. **Metrics column** — P&L totals (tabular `pnlTotals` style), cumulative P&L chart, age-comp
   (consumer labels Peak / Good / Markdown), inventory, orders, impact stats, sales/demand, spoil.
4. **Belief column** — freshness × time, histogram, OperatorBar.
5. **Sidebar** — `ObsControlsPane` (channels, preset, truth toggle) + redesigned `EventsPane`.
6. **Reference drawer** — Controller tab with tradeoff curve/histogram; `?` opens shortcuts;
   visible header triggers removed.
7. **Tuning dock** — Observation tab retired; logistics calendar Sunday-first with blue delivery /
   orange order fills.
8. **Hidden hosts** — `#chart-sales`, `#chart-stockout` remain for hover-link wiring.

## Alternatives considered

- **Keep v5 Secondary chrome** — rejected: obs controls duplicate sidebar intent; tradeoff charts
  too tall beside histogram.
- **Four-column grid** — rejected: tuning dock already provides deep teaching plots.
- **Remove hidden sales/stockout charts** — rejected: hover-link and regression tests depend on ids.

## Consequences

- **Easier** — single metrics stack; obs controls beside events; tradeoff in reference drawer.
- **Harder** — `studioLogic.ts` mount graph churn; EventsPane + e2e selector updates.
- **Locked in** — `.cockpit-pane--primary/secondary/economics/today` retired from shell.
- **Supersedes** — layout v5 grid areas and SecondaryChrome as primary obs/tradeoff surface.
