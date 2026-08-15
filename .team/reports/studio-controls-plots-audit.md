# Studio controls ↔ plots audit

**Date:** 2026-08-15  
**Ticket:** T-119 (architect) — report-only milestone (repeat audit)  
**Audit baseline:** `main` @ `558236e` (2026-08-15). Sources read from worktree `.worktrees/T-119-architect` at this commit.  
**Supersedes:** T-102 audit draft (`team/T-102/architect` @ `d74e8c6`, baseline `0b874be` via `git show`).  
**Method:** Static wiring trace (`controls.ts`, `sections.ts`, `main.ts`, `types.ts`, `engine/projector.ts`, `charts/*.ts`) plus code-inferred update tiers.  
**Deferred:** Knowledge-scenario layout audit — see [T-118 report](./studio-knowledge-scenario-audit.md) on `team/T-118/architect` (cross-reference only).

---

## Executive summary

| # | Criterion | Verdict | Headline |
|---|-----------|---------|----------|
| 1 | No redundant controls | **FAIL** | Duplicate obs-scenario callbacks; `sensor_sigma` slider with no chart feedback; policy chip auto-sets `intervalMs` while a separate interval control exists |
| 2 | Every control affects a plot | **FAIL** | Staged/operational knobs (`seed`, `starting_inv`, `demand_*`, `sensor_sigma`, `intervalMs`, order qty before Advance) do not move any visible chart on input |
| 3 | Every plot is relevant | **PASS** | Each plot teaches a distinct inventory / belief / calendar / economics concept |
| 4 | All relevant concepts illustrated | **PARTIAL FAIL** | Core studio concepts covered; `window_days` and `lead_time` have no UI; `sensor_sigma` UI over-promises; pipeline / VOI axes out of scope |
| 5 | No redundant plots | **FAIL** | Belief heatmap duplicated (Play vs Belief); P&L rendered in three surfaces (totals + sparkline + Pricing series) |

**Overall:** Verdicts unchanged from the T-102 pass on `0b874be`. Sectioning remains pedagogically strong; control↔plot coupling gaps and duplication clusters persist. One product change landed on `main` since T-102 (cumulative P&L lines) — see [Delta since T-102](#delta-since-t-102-audit-0b874be).

---

## Delta since T-102 audit (`0b874be`)

| Commit | Change | Audit impact |
|--------|--------|--------------|
| `558236e` | PnL sparkline (`#chart-pnl-spark`) and Pricing focus chart (`plot-pnl`) now plot **cumulative** revenue/cost/profit via `cumulativePnLSeries()` in `pnlTimeseries.ts`; tests added | **Criterion 5:** still three P&L surfaces, but spark + focus now share the same cumulative semantics (reduces daily-vs-cumulative confusion). Totals chrome remains aggregate cards. **No change** to FAIL verdict. |
| `0b874be` | Truth-vs-belief audit doc + obs-scenario belief trail fix | Cross-ref [truth-vs-belief-audit.md](./truth-vs-belief-audit.md); mid-episode `setObsScenario` catch-up confirmed in `main.ts` |

---

## Concept inventory

From ADRs **0110**, **0114**, **0117** and section blurbs (`sections.ts`):

| Concept | ADR / source | Illustrated by | UI control(s) |
|---------|--------------|----------------|---------------|
| Day-by-day store operation | ENG-01 / Play blurb | Store marginals, history, Play focus plots | Advance, Autopilot, order qty |
| Observation / knowledge ladder P0→F2 | ADR 0110 | Belief heatmaps, filter-driven orders (via engine) | Belief obs-scenario chips |
| MWF calendar + protection 3/3/4 | ADR 0114 | Demand DOW chart, weekday/delivery chrome | *(schedule from engine; no LT dial)* |
| Controller / Autopilot | ADR 0117 | Controller orders, inventory vs target | Policy + budget knobs, Autopilot |
| Weibull spoilage + Q10 temps | Physics blurb | Survival curve + lot rug | β, η_ref, Q10, T_ref, T_store, σ |
| Demand mean & variability | Demand blurb | Sales vs demand, DOW profile | demand μ, demand V/M |
| Logistics / base-stock | Logistics blurb | Inventory vs target, age bands | case size, base-stock, starting inv |
| MOD-21 arrival corridors | Arrival blurb | Arrival prior + ΔT shift | Arrival product chips, spread_scale, transit ΔT, F2a SD |
| Economics / P&L | Pricing blurb | PnL totals, sparkline, Pricing series | p_sell, c_unit, c_waste, c_stockout |
| Belief age×count density | Belief blurb | Age marginal + large heatmap | obs scenario (engine), truth overlay |
| Truth vs belief presentation | ADR 0125 / T-115 audit | Lots chart, belief overlays, inventory source | Sim truth overlay toggle |
| Episode seed / CRN | ADR 0068 | All plots after Reset | seed slider |
| Reserved sensor noise | types.ts comment | *(sim only)* | sensor σ slider |

**Not illustrated (acceptable deferrals):** VOI sweep axes (ADR 0006), pipeline Gantt (explicitly excluded in Arrival hint), SCN-P2 (ADR 0022 Out).

**Missing UI for in-scope SimConfig fields:** `window_days` (rolling chart window), `lead_time` (ADR 0114 fixed at 1 for v1 but still a config field).

---

## Update tiers (code-inferred)

| Tier | Meaning | Re-render path |
|------|---------|----------------|
| **Instant local** | Projector-only, no engine | `setEconomics` → `renderChrome` (+ Pricing plot if visible) |
| **Staged preview** | `setConfig` + `renderActiveFocusPlots` | Physics / Arrival / Logistics target lines; survival & arrival PDFs read staged `vm.config` |
| **Overlay** | Presentation gate | `showTruth` → `renderAll` (`historyForCharts`, `truthLots`, belief captions) |
| **Per act / Advance** | Engine `act` / `step_n` → `applyDelta` | Store, belief, orders, P&L history |
| **Engine round-trip** | Async adapter | Reset, obs-scenario catch-up (`setObsScenario`) |
| **Operational** | Chrome / loop only | Autopilot interval, Play/Pause, Advance/Reset buttons |

**Latency (typical):** instant local & staged preview < one frame; Advance/Autopilot 500 ms–2 s+ (adapter + `intervalMs`); Reset/init seconds (Pyodide/WASM boot path); obs-scenario catch-up variable (chips disabled, progress hint shown).

---

## Control → plot matrix

| Section | Control ID | Update tier | Affected plots / chrome | Latency |
|---------|------------|-------------|-------------------------|---------|
| Run | `order-range` / `order-num` | Per act | `plot-controller-orders`, store series, P&L, inventory *(after Advance/Autopilot)* | On next step |
| Run | `btn-advance` | Per act | All store + focus + P&L | Async |
| Run | `btn-autopilot-play` / `pause` | Operational | Same as act loop | Async loop |
| Run | `btn-reset` | Engine RT | All plots | Async |
| Run | `btn-show-truth` | Overlay | `#chart-history`, belief heatmaps, survival rug, arrival rug, inventory, age-comp | Instant |
| Run | *(meta)* weekday / delivery hint | — | Text only | On step |
| Play | `seed` | Engine RT *(Reset)* | All plots post-Reset | Async |
| Pricing | `p_sell`, `c_unit`, `c_waste`, `c_stockout` | Instant local | `#chart-pnl-totals`, `#chart-pnl-spark`, `plot-pnl` | Instant |
| Physics | `beta`, `eta_ref`, `q10`, `t_ref_c`, `t_store_c`, `sigma` | Staged preview *(survival)* + Reset *(sim)* | `plot-survival`; store needs Reset/Advance | Preview instant |
| Demand | `demand_mu`, `demand_vm` | Engine RT *(Reset only)* | `plot-demand` uses `vm.demand_summary` snapshot — **no preview on slider** | Reset only |
| Logistics | `case_size` | Staged + order snap | Order chrome, `plot-inventory` target semantics | Instant chrome |
| Logistics | `base_stock` | Staged preview | `plot-inventory` target line | Instant |
| Logistics | `starting_inv` | Engine RT | Store / inventory history | Reset only |
| Arrival | `arrival-chips` | Staged preview + Reset | `plot-arrival-prior`, `plot-arrival-shift` | Preview instant |
| Arrival | `spread_scale`, `transit_temp_bias_c`, `f2a_transit_sd` | Staged preview + Reset | Arrival plots | Preview instant |
| Arrival | `sensor_sigma` | Reset *(sim)* | **No chart reads `sensor_sigma`** | Reset only; no visual |
| Belief | obs-scenario chips | Engine RT *(catch-up)* | Belief plots, filter-driven future orders | Async catch-up |
| Controller | policy chips | Per act + sets `intervalMs` | `plot-controller-orders` | Next act |
| Controller | `alpha`, `rho`, `H`, `n_rollout_paths`, `candidate_case_radius`, `n_particles` | Per act | Orders / inventory indirectly | Next act |
| Controller | `intervalMs` | Operational | **None** — wall-clock only | N/A |

---

## Plot → control matrix

| Plot ID | DOM container | Section(s) | Driving controls | Primary ViewModel fields | Teaching purpose |
|---------|---------------|------------|------------------|----------------------------|------------------|
| *(store)* sales | `#chart-sales` | Always (Play context) | Advance, Autopilot, physics/demand/logistics *(via sim)* | `history[].sales_total` | Daily sales rhythm |
| *(store)* stockout | `#chart-stockout` | Always | Same | `history[].stockout` | Missed sales / stockouts |
| *(store)* lots | `#chart-history` | Always | Truth overlay; Advance | `history[].lots`, `age_at_receipt` *(gated)* | Cohort age structure |
| *(store)* spoilage | `#chart-spoil` | Always | Advance | `history[].waste_total` | Spoilage totals |
| *(chrome)* PnL totals | `#chart-pnl-totals` | Always | Pricing sliders | `pnl_totals`, `episode_day` | Window + today economics |
| *(chrome)* PnL spark | `#chart-pnl-spark` | Always | Pricing sliders | `pnl_series` *(cumulative display)* | Cumulative profit trajectory |
| `plot-belief` | `#chart-belief` | Play | Obs scenario, truth overlay, Advance | `belief`, `live_lots` | Compact belief vs truth |
| `plot-sales-demand` | `#chart-sales-demand` | Play | Advance | `history` sales/demand/stockout | Fill rate vs demand |
| `plot-pnl` | `#chart-pnl-series` | Pricing | Pricing sliders | `pnl_series` *(cumulative display)* | Full cumulative revenue/cost/profit |
| `plot-survival` | `#chart-survival` | Physics | Physics sliders, truth overlay | `config`, `live_lots` | Spoilage law + cohort ages |
| `plot-demand` | `#chart-demand` | Demand | Reset *(demand_summary)* | `demand_summary`, `schedule` | DOW demand + 3/3/4 protection |
| `plot-inventory` | `#chart-inventory` | Logistics, Controller | base_stock, case_size, truth overlay, Advance/Autopilot | `history` or `belief_history`, `config` | On-hand vs target |
| `plot-age-comp` | `#chart-age-comp` | Logistics | truth overlay, Advance | `history` or `belief_history` | Age-band composition |
| `plot-arrival-prior` | `#chart-arrival-prior` | Arrival | Arrival knobs/chips, truth overlay | `config`, `history` receipts | Arrival-age prior + samples |
| `plot-arrival-shift` | `#chart-arrival-shift` | Arrival | `transit_temp_bias_c` | `config` | MOD-18 Arrhenius teaching |
| `plot-belief-age-marginal` | `#chart-belief-age-marginal` | Belief | Obs scenario, Advance | `belief.age_marginal` | Age marginal (ADR 0109) |
| `plot-belief-lg` | `#chart-belief-lg` | Belief | Same as compact belief | `belief`, `live_lots` | Primary belief heatmap |
| `plot-controller-orders` | `#chart-controller-orders` | Controller | Controller knobs, order qty, Advance/Autopilot | `history[].order_qty` | Policy output trace |

---

## Findings

### Criterion 1 — No redundant controls

| Tag | Finding | Evidence |
|-----|---------|----------|
| **FAIL** | `onSetObsScenario` and `onObsScenario` both fire on chip click; only `onSetObsScenario` is wired in `main.ts` | `controls.ts` L609–614; `main.ts` L681–719 |
| **FAIL** | `sensor_sigma` slider exposed in Arrival section but no chart consumes it (reserved sim knob) | `types.ts` L76–79; `arrivalPrior.ts` uses prior PDF / receipt rug only |
| **AMBIGUOUS** | Policy chip sets `intervalMs` via `defaultIntervalMsForPolicy` while a separate interval control exists | `controls.ts` L625–634, `autopilotLoop.ts` |
| **PASS** | Section-scoped control blocks avoid showing unrelated sliders at once | `mountSectionControls` `showSection` |

### Criterion 2 — Every control affects a plot

| Tag | Finding | Evidence |
|-----|---------|----------|
| **FAIL** | `demand_mu` / `demand_vm` sliders do not update `plot-demand` on input; chart reads `vm.demand_summary` from Snapshot | `demandDist.ts` L65–68; `projector.ts` `demandSummary` not updated in `setConfig` |
| **FAIL** | `sensor_sigma` — no plot feedback | — |
| **FAIL** | `intervalMs` — operational only; no chart | `autopilotLoop` `getIntervalMs` |
| **AMBIGUOUS** | `seed`, `starting_inv` — affect all plots only after **Reset** (dirty banner present) | Play hint; dirty banner in play chrome |
| **AMBIGUOUS** | Order qty — affects plots only on next Advance/Autopilot | `onOrderChange` stores local state only |
| **PASS** | Pricing sliders instantly reproject all P&L surfaces | `main.ts` `onEconomicsChange` L655–663 |
| **PASS** | Physics / arrival staged sliders instantly refresh survival & arrival focus plots | `renderActiveFocusPlots` |

### Criterion 3 — Every plot is relevant

| Tag | Finding | Evidence |
|-----|---------|----------|
| **PASS** | Store stack + section focus plots each map to one teaching goal in section blurbs | `sections.ts` |
| **PASS** | Missed-sales marginal (T-116) complements sales chart | `main.ts` `#chart-stockout` |
| **PASS** | Shared `plot-inventory` in Logistics + Controller is intentional | `sections.ts` logistics + controller `plotIds` |

### Criterion 4 — All relevant concepts illustrated

| Tag | Finding | Evidence |
|-----|---------|----------|
| **FAIL** | `window_days` in `SimConfig` — no control; sets rolling window silently | `types.ts` L60; `projector.ts` `windowDays` |
| **AMBIGUOUS** | `lead_time` — no UI; ADR 0114 v1 locks LT=1 | `demandDist.ts` `protectionCoverageFromSchedule` |
| **FAIL** | `sensor_sigma` UI implies teachable arrival noise but charts omit it | `controls.ts` arrival group |
| **PASS** | Obs ladder, calendar, controller, physics, economics covered | ADRs 0110, 0114, 0117 |
| **PASS** | Truth vs belief split documented | [truth-vs-belief-audit.md](./truth-vs-belief-audit.md) |

### Criterion 5 — No redundant plots

| Tag | Finding | Evidence |
|-----|---------|----------|
| **FAIL** | `plot-belief` (Play) and `plot-belief-lg` (Belief) both call `renderBeliefAgeCount` on the same `vm.belief` | `main.ts` L409–426 |
| **FAIL** | P&L triple surface: `#chart-pnl-totals` + `#chart-pnl-spark` always visible; `plot-pnl` in Pricing — spark and focus now both cumulative (`558236e`) but still three containers | `pnlTimeseries.ts` `cumulativePnLSeries`; `renderChrome` + Pricing section |
| **AMBIGUOUS** | `plot-belief-age-marginal` is a derived view — justified for axis-aligned teaching (ADR 0109) | `beliefAgeMarginal.ts` |
| **PASS** | `plot-sales-demand` vs store sales marginal — different lens | `salesDemand.ts` |

---

## Prioritized recommendations

*(Report-only — no implementation without human approval.)*

| Priority | Action | Size | Rationale |
|----------|--------|------|-----------|
| P1 | **Remove or hide `sensor_sigma` slider** until a chart exists | **S** | Fails criteria 1 & 2 |
| P1 | **Add staged preview for Demand section** or relabel “Apply on Reset” | **M** | Demand slider ↔ plot gap |
| P2 | **Collapse belief duplication** — Play shows `plot-sales-demand` only; belief heatmap in Belief section | **M** | Criterion 5 |
| P2 | **Consolidate P&L chrome** — totals + sparkline OR Pricing full series | **S** | Criterion 5 |
| P2 | **Remove dead `onObsScenario` callback** | **S** | Criterion 1 |
| P3 | **Expose `window_days` read-only** in Play meta | **S** | Criterion 4 |
| P3 | **Relabel operational knobs** with tier badges | **S** | Clarifies criterion 2 |
| P3 | **Decouple policy chip from `intervalMs`** | **S** | Criterion 1 ambiguity |
| Defer | Lead time dial when ADR 0114 LT≠1 opens | **L** | Locked |
| Defer | Knowledge-scenario layout | **L** | [T-118 audit](./studio-knowledge-scenario-audit.md) |

---

## Manual walkthrough notes

**Status:** Code-inferred (no browser automation this pass).

| Action | Expected plot behavior |
|--------|------------------------|
| Move Pricing sliders | PnL totals + cumulative sparkline update immediately; Pricing cumulative series if open |
| Move Physics sliders | Survival curve updates immediately; store unchanged until Advance |
| Move Demand sliders | Dirty banner; **demand chart unchanged** until Reset |
| Move Arrival sliders/chips | Arrival prior/shift update immediately |
| Toggle Sim truth overlay | Lots chart populates; belief markers; inventory belief↔truth |
| Advance / Autopilot | All store charts, belief, orders, P&L append |
| Reset | Full regen from seed + staged config |
| Obs scenario chip | Catch-up spinner; belief plots refresh |

---

## Cross-references

- [truth-vs-belief-audit.md](./truth-vs-belief-audit.md) — truth overlay wiring (landed on `main`)
- [studio-knowledge-scenario-audit.md](./studio-knowledge-scenario-audit.md) — T-118 on `team/T-118/architect` (layout per scenario; separate milestone)
- T-102 audit draft superseded by this report

---

## Process notes

- Worktree: `.worktrees/T-119-architect` @ `558236e` = `main` tip at audit time.
- Branch: `team/T-119/architect`.
- Remediation pending human approval.
