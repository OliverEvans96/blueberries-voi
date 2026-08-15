# Studio knowledge-scenario UI audit

**Date:** 2026-08-15  
**Ticket:** T-119 (architect, report-only) — **repeat audit** (supersedes T-118 @ `0b874be`)  
**Baseline:** `main` @ `558236e`  
**Scope:** Whether the interactive studio should differ across knowledge scenarios
(`P0 | P1 | F1 | F1s | F2a | F2`). Cross-ref ADR 0086 present-field table, ADR 0110/0123
ladder wiring, ADR 0125 show-truth deferral, and [truth-vs-belief-audit.md](./truth-vs-belief-audit.md).

**Method:** Read-only pass on `main` @ `558236e` — `web/src/main.ts`, `sections.ts`,
`controls.ts`, `showTruth.ts`, all `web/src/charts/*`, `filter/types.py` `_SCENARIO_PRESENT`,
plus existing vitest guards in `studioScenarios.test.ts`.

**Prior report:** T-118 audit on `0b874be` ([same path](./studio-knowledge-scenario-audit.md),
branch `team/T-118/architect`, commit `fde7e5b`).

---

## Executive summary

**Verdict: single-shell layout is correct; scenario-aware availability gating is still missing.**

The studio satisfies the backlog preference for **one consistent layout** across all six
knowledge rungs. Section nav, store column, and focus-pane plot slots are identical regardless
of `obs_scenario`. Observation chips live only under Belief; lazy catch-up (ADR 0123) retargets
the filter without forking chrome. **No layout forks were found.**

What is missing is a declarative **`scenarioAvailability` map** (plot + control × scenario) that
marks or hides surfaces a produce manager would not see under a given mask — complementary to
the global `showTruth` gate from T-115. Today:

| Gap class | Severity | Example |
|-----------|----------|---------|
| Books charts draw unobserved fields | **Medium** | Spoilage bar uses `waste_total` on P0 (waste masked) |
| Truth geometry shown without overlay gate | **Medium** | Arrival receipt rug uses `age_at_receipt` history for all scenarios; only F2 observes it |
| Scenario-specific knobs always visible | **Low** | `f2a_transit_sd`, `sensor_sigma` in Arrival for every rung |
| No “unavailable” affordance on low-value plots | **Low** | F2a dashed prior always drawn; teaching value varies by rung |
| Engine path correct; UI presentation lags | **Info** | Filter masks per ADR 0086; charts do not read `obs_scenario` |

**Recommendation:** Accept V1 shell as-is for teaching the ladder; implement remediation as a
small follow-on (e.g. **T-120** or human-chosen id) adding `scenarioAvailability` in JS only —
**no section reorder, no alternate HTML templates**.

---

## Delta vs T-118 (`0b874be` → `558236e`)

One commit landed on `main` between audits:

| Commit | Change | Scenario-audit impact |
|--------|--------|------------------------|
| `558236e` | PnL sparkline + Pricing focus chart now plot **cumulative** revenue/cost/profit (`cumulativePnLSeries` in `pnlTimeseries.ts`; captions updated in `main.ts`) | **None on gating.** PnL slots remain **Show** at all rungs; presentation-only. |

**Unchanged since T-118:** `_SCENARIO_PRESENT`, `sections.ts` plot lists, `showTruth` gate,
spoilage-on-P0 leak, arrival receipt rug without F2/scenario gate, scenario-blind chart layer,
Arrival slider visibility, ladder chips / catch-up wiring. **Findings and remediation plan are
unchanged** aside from the cumulative PnL note above.

---

## Cross-reference: ADR 0086 vs UI

Python `_SCENARIO_PRESENT` (authoritative mask):

| Field | P0 | P1 | F1 | F1s | F2a | F2 |
|-------|:--:|:--:|:--:|:---:|:---:|:--:|
| `arrivals` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sales_total` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `waste_total` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sales_by_lot` | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| `waste_by_lot` | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| `pack_date` | ✗ | ✗ | ✗ | ✗ | ✓ | (subsumed) |
| `age_at_receipt` | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| `lot_ids_live` | weak | weak | ✓ | ✓ | weak | ✓ |

Studio charts today consume **ViewModel history** (richest sim log) and **belief**, gated only by
`showTruth` for hidden-state geometry — not by `config.obs_scenario`. ADR 0125 explicitly deferred
per-scenario chrome to this audit line.

---

## Plot × scenario matrix

**Legend:** **Show** = appropriate for manager mode at this rung · **Gate** = keep slot, dim or
caption “not observed” · **Overlay** = needs `showTruth` or scenario gate · **N/A** = low teaching
value but harmless.

| Plot / slot | Section | P0 | P1 | F1 | F1s | F2a | F2 | Notes |
|-------------|---------|----|----|----|----|-----|-----|-------|
| Units sold | Store | Show | Show | Show | Show | Show | Show | `sales_total` observed all rungs |
| Missed sales | Store | Show | Show | Show | Show | Show | Show | `stockout` derived from observed demand/sales |
| Lots · day × age | Store | Overlay | Overlay | Gate | Gate | Overlay | Gate | Lot maps observed F1/F1s/F2; chart strips lots unless `showTruth` — does not distinguish lot-resolved obs vs truth overlay |
| Spoilage | Store | **Gate** | Show | Show | Show | Show | Show | **P0:** `waste_total` not in mask; chart still plots sim waste |
| Profit totals + spark | Run | Show | Show | Show | Show | Show | Show | Books / economics; spark is **cumulative** since `558236e` |
| Belief (compact) | Play | Show | Show | Show | Show | Show | Show | Posterior always meaningful; sharpens up-ladder |
| Sales vs demand | Play | Show | Show | Show | Show | Show | Show | Observed totals |
| Revenue · cost · profit | Pricing | Show | Show | Show | Show | Show | Show | **Cumulative** lines since `558236e`; JS reprojection |
| Survival + lot rug | Physics | Overlay | Overlay | Overlay | Overlay | Overlay | Overlay | Prior is config; rug is truth — ADR 0125 gated |
| DOW demand | Demand | Show | Show | Show | Show | Show | Show | Config teaching |
| Inventory vs base-stock | Logistics / Controller | Show | Show | Show | Show | Show | Show | Belief path when `showTruth=false` (T-115) |
| On-hand by age band | Logistics | Show | Show | Show | Show | Show | Show | Belief bands when overlay off |
| Arrival-age prior + rug | Arrival | N/A | N/A | N/A | N/A | **Show** | **Show** | F2a narrows prior (dashed curve always drawn); receipt rug uses `age_at_receipt` from history — **observed only on F2**, else truth leak |
| Transit ΔT shift | Arrival | Show | Show | Show | Show | Show | Show | Config-only |
| Age marginal | Belief | Show | Show | Show | Show | Show | Show | Belief |
| Belief heatmap (lg) | Belief | Show | Show | Show | Show | Show | Show | Truth markers gated by `showTruth` |
| Controller orders | Controller | Show | Show | Show | Show | Show | Show | Orders are books |

**Layout fork check:** `STUDIO_SECTIONS` plot lists are static (`sections.ts`); `setSection` toggles
`hidden` on the same DOM nodes for every scenario. **PASS — no fork.**

---

## Control × scenario matrix

| Control / knob | Location | P0 | P1 | F1 | F1s | F2a | F2 | Notes |
|----------------|----------|----|----|----|----|-----|-----|-------|
| Order qty / Advance / Reset / Autopilot | Run | Show | Show | Show | Show | Show | Show | Episode mechanics |
| Sim truth overlay | Run | Show | Show | Show | Show | Show | Show | Global gate (ADR 0125) |
| Seed | Play | Show | Show | Show | Show | Show | Show | Reset-gated |
| Economics sliders | Pricing | Show | Show | Show | Show | Show | Show | Local reproject |
| Physics sliders (β, η, Q10, temps, σ) | Physics | Show | Show | Show | Show | Show | Show | Reset-gated |
| Demand μ, V/M | Demand | Show | Show | Show | Show | Show | Show | Reset-gated |
| Case size, base-stock, starting inv | Logistics | Show | Show | Show | Show | Show | Show | Reset-gated |
| Arrival product chips | Arrival | Show | Show | Show | Show | Show | Show | MOD-21 teaching |
| `spread_scale`, `transit_temp_bias_c` | Arrival | Show | Show | Show | Show | Show | Show | Affects prior for all |
| **`f2a_transit_sd`** | Arrival | **Gate** | **Gate** | **Gate** | **Gate** | **Show** | N/A | Only F2a mask uses `pack_date` prior width |
| **`sensor_sigma`** | Arrival | **Gate** | **Gate** | **Gate** | **Gate** | **Gate** | **Show** | Models receipt-age measurement noise (F2) |
| Observation scenario chips | Belief | Show | Show | Show | Show | Show | Show | ADR 0123 live catch-up |
| Controller / Autopilot budgets | Controller | Show | Show | Show | Show | Show | Show | Policy follows active belief |

**Redundancy note (out of scope):** separate backlog item *Frontend controls/plots audit*
covers cross-section control relevance; this matrix is scenario-specific only.

---

## Six rung narratives (what the UI should teach)

### P0 — Books only

**Filter sees:** receipts + POS sales totals (`arrivals`, `sales_total`).  
**Teaching goal:** baseline inventory control with no shrink signal — belief must infer waste.  
**UI today:** Belief widens (mock blur 1.6); chips and belief plots work. **Spoilage store chart
still plots daily waste** as if books included shrink — contradicts “books only” story unless user
enables truth overlay knowing it is sim ground truth.

### P1 — Shrink gun (default)

**Filter sees:** P0 + storewide `waste_total`.  
**Teaching goal:** daily shrink totals tighten age/mass belief.  
**UI today:** Default `obs_scenario`; spoilage chart aligns with mask. Reference rung for
comparisons.

### F1 — Lot ID at POS

**Filter sees:** P1 + `sales_by_lot`, `lot_ids_live`.  
**Teaching goal:** lot-resolved sales identify which cohorts sold.  
**UI today:** Belief sharpens; lot day×age chart remains truth-gated (`showTruth`), not
“observed lot map” gated — no distinct visual for POS-resolved vs hidden-state lots.

### F1s — Lot ID on shrink

**Filter sees:** P1 + `waste_by_lot`, `lot_ids_live`.  
**Teaching goal:** shrink attribution by lot (MOD-17 path).  
**UI today:** Same lot-chart caveat as F1; spoilage aggregate chart does not break out by lot
(no teaching surface for `waste_by_lot` — acceptable gap unless a lot-level shrink viz is added
later).

### F2a — Pack date on ASN

**Filter sees:** P1 + `pack_date` (narrows arrival-age prior, no measured receipt age).  
**Teaching goal:** ASN metadata tightens prior before goods arrive.  
**UI today:** Arrival section always shows dashed F2a prior curve and `f2a_transit_sd` slider —
appropriate here. Receipt-age rug still plots when history contains `age_at_receipt` (sim truth)
even though F2a does not observe measured age — **manager-mode leak** unless gated.

### F2 — Age at receipt

**Filter sees:** richest map — `age_at_receipt`, lot maps, totals.  
**Teaching goal:** measured freshness at receipt plus rich maps.  
**UI today:** Receipt rug and `sensor_sigma` are scientifically on-target; survival/inventory
belief paths reflect sharper posterior. Truth overlay remains optional debug layer.

---

## Findings (ordered by severity)

### Medium — manager information set leaks

1. **Store spoilage on P0** — `renderMarginal(..., "spoilage")` always reads `history[].waste_total`
   (`marginals.ts`). Under P0 mask the manager does not observe waste; chart presents it in the
   always-visible store column without caption or hide. Extends T-115 “Obs” classification — spoilage
   should be scenario-gated or labeled “sim truth / not in books”.

2. **Arrival receipt rug without F2** — `recentReceiptAges()` in `arrivalPrior.ts` plots
   `age_at_receipt` ticks for any history row with deliveries. Only F2 observes receipt age; for
   P0–F2a the rug is hidden-state geometry (like lots chart) but is **not** gated by `showTruth`
   or `obs_scenario`.

### Low — scenario-specific controls always enabled

3. **`f2a_transit_sd` slider** visible in Arrival section for P0–F2 — affects filter prior width
   only when F2a mask active; staging still dirty-until-reset like other config. Teaching noise on
   non-F2a rungs.

4. **`sensor_sigma` slider** visible except meaningful for F2 receipt-age likelihood — same pattern.

5. **F2a dashed prior curve** always rendered in Arrival focus plot — harmless but low signal on
   P0/P1; could use `scenarioAvailability` to dim caption “F2a only”.

### Low — consistency / polish

6. **No chart reads `vm.config.obs_scenario`** — entire presentation layer is scenario-blind except
   chip chrome and catch-up progress (`controls.ts`). Engine + ADR 0123 path is correct; UI does not
   mirror mask semantics.

7. **Legend `.chip-spoil` always visible** in store — analogous to T-115 lots-chip note; worse on
   P0 where spoilage is not observed.

8. **Play section shows compact belief + sales-demand** for all rungs — acceptable; belief diff
   is the primary ladder teaching surface.

### Info — already good

9. **Single shell / no layout forks** — `sections.ts`, `main.ts` template, eight nav items fixed.
10. **Ladder chips** — six ids, locked copy, no P2 (`controls.ts`, `studioScenarios.test.ts`).
11. **Lazy scenario switch** — `main.ts` `onSetObsScenario` + catch-up banner; not dirty-until-reset
    (ADR 0123 superseding 0110).
12. **Truth overlay independence** — `showTruth.ts` global; ADR 0125 compliant; orthogonal to ladder.
13. **Cumulative PnL (`558236e`)** — Run spark + Pricing focus chart align on cumulative semantics;
    does not affect scenario availability.

---

## Remediation plan (pending human approval)

Implement in a **follow-on ticket** (e.g. **T-120**) — not T-119. Keep **one layout**; add a small
module e.g. `web/src/scenarioAvailability.ts`:

```ts
export type ScenarioId = /* re-export from types */;

export type Availability = "show" | "dim" | "unavailable";

export const PLOT_AVAILABILITY: Record<string, Record<ScenarioId, Availability>> = {
  "store-spoilage": { P0: "unavailable", P1: "show", /* ... */ },
  "plot-arrival-prior-rug": { /* F2: show; others: unavailable unless showTruth */ },
  // ...
};

export const CONTROL_AVAILABILITY: Record<string, Record<ScenarioId, Availability>> = {
  f2a_transit_sd: { P0: "dim", P1: "dim", F1: "dim", F1s: "dim", F2a: "show", F2: "dim" },
  sensor_sigma: { P0: "dim", P1: "dim", F1: "dim", F1s: "dim", F2a: "dim", F2: "show" },
};
```

**Integration points (smallest diff):**

| Hook | Change |
|------|--------|
| `main.ts` `renderStore` | Skip or placeholder spoilage when P0; optional caption via `data-unavailable` |
| `main.ts` `renderActiveFocusPlots` | Pass `obs_scenario` into arrival prior or pre-filter rug samples |
| `controls.ts` `syncConfig` | Disable/dim sliders when `CONTROL_AVAILABILITY[id][scenario] !== "show"` |
| `sections.ts` | **Do not** change `plotIds` per scenario — use dim/unavailable styling inside slots |
| Tests | Extend `studioScenarios.test.ts` or add `scenarioAvailability.test.ts` for map completeness |

**Explicit non-goals:**

- No alternate section lists or nav items per scenario
- No Python / wire protocol changes
- No replacement for `showTruth` — scenario gate handles *observed vs unobserved fields*; truth
  overlay remains debug/education for hidden state
- SCN-P2 stays Out

**Estimated scope:** one implement ticket (~1–2 files production + tests), reviewer + verify on
web vitest only.

---

## T-115 deferral closure

| T-115 deferred item | T-119 status |
|---------------------|--------------|
| Knowledge-scenario UI audit | **Addressed** (this report; repeat confirms T-118) |
| F2 receipt ages as “observed” vs hidden | Finding #2 — rug ungated |
| Per-scenario chrome vs global showTruth | Remediation proposes layered gates |

ADR 0125 checklist item 6 (“Defer knowledge-scenario-specific chrome”) can be marked satisfied at
the audit level; implementation remains optional follow-on.

---

## Audit criteria scorecard (T-119)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Consistent layout (single shell) | **PASS** |
| 2 | Charts scenario-appropriate per P0–F2 | **PARTIAL** — medium leaks (spoilage P0, arrival rug) |
| 3 | Controls scenario-appropriate | **PARTIAL** — Arrival sliders always visible |
| 4 | Concept coverage per rung | **PASS** — belief/chips teach ladder; some field-level viz gaps acceptable |
| 5 | Availability vs fork (`scenarioAvailability`; no layout forks) | **FAIL map / PASS fork** — no `scenarioAvailability`; no forks |

---

## Subagent / source index

| Source | Role |
|--------|------|
| `web/src/main.ts` | Shell template, render paths, `historyForCharts`, scenario catch-up |
| `web/src/sections.ts` | Static section → plot mapping |
| `web/src/controls.ts` | Chips, sliders, catch-up UX |
| `web/src/showTruth.ts` | Global truth overlay gate |
| `web/src/charts/*` | Per-chart data bindings |
| `src/blueberries_voi/filter/types.py` | `_SCENARIO_PRESENT` |
| `.team/reports/truth-vs-belief-audit.md` | Prior chart matrix + deferral |
| ADR 0086, 0110, 0123, 0125 | Mask table, ladder, lazy catch-up, show-truth |

**Audit-only commit:** T-119 architect worktree @ `558236e`; no production files modified.

**Supersedes:** T-118 report-only audit @ `0b874be` (same findings; one PnL presentation delta).
