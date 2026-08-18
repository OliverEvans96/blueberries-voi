# T-130 gap audit — 30-item user feedback checklist

**Branch:** `team/T-130/implement`  
**Worktree:** `.worktrees/T-130-implement`  
**Audit date:** 2026-08-17  
**Source plan:** `t-129_layout_round_3_84522d2a.plan.md`

## Summary

| Status | Count |
|--------|------:|
| DONE | 29 |
| DEFER | 1 (#17) |
| PARTIAL | 0 |
| MISSING | 0 |

All non-deferred user feedback items are implemented. Item #17 (DOW variance charts / stronger slider reactivity) remains explicitly deferred per user priority.

---

## Checklist

| # | Request | Status | Evidence |
|---|---------|--------|----------|
| 1 | Today: remove units sold & missed sales (keep hidden hosts OK) | **DONE** | `StudioLayout.tsx` L163–178: `#chart-sales` / `#chart-stockout` in `.visually-hidden`; visible Today strip is inventory + orders + age-comp only |
| 2 | Today: keep inventory vs base-stock + order quantity | **DONE** | `StudioLayout.tsx` L136–152: `#chart-inventory`, `#chart-controller-orders` |
| 3 | Order quantity = bar chart not line | **DONE** | `controllerOrders.ts` L74–80: `.order-bar` `rect` elements via `d3.scaleBand` |
| 4 | Today charts full width, shorter height | **DONE** | `cockpitGrid.css` L115–130: `.run-today-charts` 1-column stack; `.chart--compact` `min-height: 72px` |
| 5 | Tradeoff + histogram update on obs scenario change | **DONE** | `studioLogic.ts` `applyObsSelection` L823–864 → `refreshRemotePanes()` L635–638 → `fetchTradeoffForecast()`; `SecondaryChrome.tradeoff.test.ts` rerender on new forecasts |
| 6 | Tradeoff + histogram bigger / full width | **DONE** | `cockpitGrid.css` L159–195: `.secondary-chrome-tradeoff` / `.tradeoff-chart-host` `min-height: 200px`, `width: 100%` |
| 7 | Events on right, Today in center | **DONE** | `cockpitGrid.css` L14–17: v5 areas `economics today events`; events `grid-row: 1 / span 3` |
| 8 | Obs scenario selector + sim-truth toggle above OperatorBar | **DONE** | `SecondaryChrome.tsx` obs chips + truth toggle; `StudioLayout.test.ts` chrome host precedes `#operator-bar-host` |
| 9 | Tradeoff curve + histogram tab toggle on Secondary | **DONE** | `SecondaryChrome.tsx` L102–149: Curve \| Histogram tab strip; single visible host |
| 10 | Row: Economics · Today · Events (right column) | **DONE** | `cockpitGrid.css` L16; `StudioLayout.test.ts` row 2 hosts |
| 11 | Keep sim-parameters width; Events gets full right column | **DONE** | Tuning spans cols 1–2 (`tuning tuning events`); events column 280–380px |
| 12 | Sim-parameters title + tabs CSS errors fixed | **DONE** | `tuningDock.css`: `.tuning-cluster-tabs [role=tab]`, `.focus-header` spacing; imported via `styles.css` |
| 13 | On-hand by age band moved Logistics → Today | **DONE** | `StudioLayout.tsx` L154–160 `#chart-age-comp` in Today; `sections.ts` logistics `plotIds` has no age-comp |
| 14 | Picking slider = 1/σ (label + axis) | **DONE** | `controls.ts` L189–198 label `Picking selectivity (1/σ)`; `paramLabels.ts` L50–54; `formatSigmaPrecision` shows `1/σ = …` |
| 15 | Mean daily demand + V/M sliders next to relevant plot | **DONE** | `controls.ts` L298–316 `.demand-controls-layout` two-column grid |
| 16 | DOW demand plot beside sliders | **DONE** | `#demand-chart-slot` in `.demand-controls-chart` column beside sliders |
| 17 | DOW reacts more / alt variance charts | **DEFER** | Low priority per user; μ preview wired via `demandPreview.ts`; V/M Reset-tier only |
| 18 | Autopilot α/ρ pad: blue crosshairs + orange handle | **DONE** | `controls.ts` L374–377 SVG crosshairs/handle; `styles.css` L1305–1317 blue crosshair + orange `#f59e0b` handle |
| 19 | α/ρ values beside pad (not far right) | **DONE** | `controls.ts` L363–382 `.alpha-rho-row` flex with `.alpha-rho-readout` adjacent to pad |
| 20 | Rollout default autopilot policy | **DONE** | `controls.ts` L114: `DEFAULT_CONTROLLER_CONTROLS.policy: "rollout"` |
| 21 | Sim-truth overlay dots scaled by lot size | **DONE** | `beliefFreshnessTime.ts` L357–362 `d3.scaleSqrt` on `lot.n`; legend "Lots (size ∝ qty)" |
| 22 | Events: daily log for manager | **DONE** | `EventsPane.tsx`: `.events-day-card`, weekday headings, typed `.events-line` rows |
| 23 | Events: protection interval since last delivery | **DONE** | `studioLogic.ts` `fetchEvents({ since_day: previousOrderDayFromSchedule(...) })` |
| 24 | Events: faint gray day dividers | **DONE** | `EventsPane.tsx` L92 `<hr className="events-day-divider" />`; `eventsPane.css` |
| 25 | Events: line item per observation | **DONE** | `.events-line--delivery`, `--sales`, `--waste`, `--stockout`, etc. |
| 26 | Events: delivery entry varies by obs scenario | **DONE** | `EventsPane.tsx` L110–125: `obsMask.age_at_receipt`, `pack_date`, `lot_ids_live` gates |
| 27 | Events: waste entry type | **DONE** | `EventsPane.tsx` L145–162 `.events-line--waste` |
| 28 | Sales/waste: omit zero lots | **DONE** | `EventsPane.tsx` L46–47 `if (qty <= 0) continue` in `formatLotBreakdown` |
| 29 | Economics chart: lines only, no points | **DONE** | `pnlTimeseries.ts` no `.pnl-dot`; `pnlTimeseries.test.ts` asserts zero circles |
| 30 | Secondary histogram: single color, not per-lot | **DONE** | `studioLogic.ts` L455 `renderFreshnessHistogram(..., "aggregated")`; `freshnessHistogram.ts` L170–171 single `--color-belief-bar` |

---

## Verification runs

```bash
cd web && npm test && npm run build && npm run e2e
```

See `.team/qa/T-130.md` for latest gate results.

## Formal DoD

| Artifact | Status |
|----------|--------|
| Spec AC | Implemented |
| `.team/qa/T-130-tests.md` | Present |
| `.team/qa/T-130.md` verify PASS | Present |
| `.team/reviews/T-130.md` APPROVED | **Missing** |
| `.team/changelog.md` T-130 entry | **Missing** |
