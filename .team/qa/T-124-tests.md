# T-124 QA — RED test map (Wave 1 fan-out)

Tracks **qa-avail**, **qa-charts**, **qa-demand**, **qa-ia** shards. Python gates N/A; web vitest only.

## AC-avail — Scenario availability (qa-avail)

| Criterion | Test | Expected RED reason |
| --- | --- | --- |
| `plotAvailability` / `controlAvailability` exports | `web/src/scenarioAvailability.test.ts` — map completeness | Module `scenarioAvailability.ts` missing |
| Map covers all plot + control ids × six rungs | same — `ALL_PLOT_IDS` / `ALL_CONTROL_IDS` | Missing registry |
| P0 spoilage unavailable | same — `store-spoilage` gate | No map |
| Arrival prior rug F2-only | same — `plot-arrival-prior-rug` | No map |
| `f2a_transit_sd` dim/show tiers | same — control gate | No map |
| `sensor_sigma` dim/show tiers | same — control gate | No map |

**RED proof:**

```bash
cd web && npm ci && npm test src/scenarioAvailability.test.ts
```

## AC-demand — Staged demand preview (qa-demand)

| Criterion | Test | Expected RED reason |
| --- | --- | --- |
| `demandSummaryFromConfig(partial)` without Reset | `web/src/engine/demandPreview.test.ts` | Method + `demandPreview.ts` missing |
| `demand_mu` slider updates `#chart-demand` in one rAF | same — staged preview wiring | No preview bind |

**RED proof:**

```bash
cd web && npm ci && npm test src/engine/demandPreview.test.ts
```

## AC-charts — Unavailable placeholder (qa-charts)

| Criterion | Test | Expected RED reason |
| --- | --- | --- |
| P0 spoilage slot uses unavailable placeholder | `web/src/react/ChartUnavailable.test.ts` | `ChartUnavailable.tsx` + gating missing |
| Muted hatch + caption affordance | same — component render | Component missing |

**RED proof:**

```bash
cd web && npm ci && npm test src/react/ChartUnavailable.test.ts
```

## AC-ia — Insight strip + decision rail (qa-ia)

| Criterion | Test | Expected RED reason |
| --- | --- | --- |
| Insight strip: day, weekday, MWF hint, scenario title, profit | `web/src/react/InsightStrip.test.ts` | Component missing |
| Decision rail: Run, obs chips, truth, P&L; chips not Belief-only | `web/src/react/DecisionRail.test.ts` | Component missing |

**RED proof:**

```bash
cd web && npm ci && npm test src/react/InsightStrip.test.ts src/react/DecisionRail.test.ts
```

## Not covered in Wave 1 QA

- AC-dedup, AC-tiers, AC-comp, AC-a11y, AC-verify — later implement / verify waves.
