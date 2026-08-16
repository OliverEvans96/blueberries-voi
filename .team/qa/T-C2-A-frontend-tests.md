# T-C2-A QA — frontend RED map (shard qa-frontend)

Focused `cd web && npm test -- src/engine/projector.test.ts src/charts/inventoryTarget.test.ts` (2026-08-16): **9 failed**, 29 passed (legacy τ tests still green).

## Coverage of acceptance criteria

### AC-frontend — `FlatBelief` uses `f_grid` / `f_marginals`; projector maps heatmap to freshness `[0, 1]`

- `web/src/engine/types.ts` `FlatBelief` carries `f_grid` / `f_marginals` (not `tau_grid` / `age_marginals`) — exercised via f-native fixtures cast into `FlatBelief`; production types still τ-only → tests hit `undefined` τ fields at runtime.
- `beliefGridFromFlat` maps `f_grid` bin centers to freshness edges in `[0, 1]` → `web/src/engine/projector.test.ts::beliefGridFromFlat f_grid / f_marginals (T-C2-A / AC-frontend) > maps f_grid bin centers to freshness edges in [0, 1], not τ-day span` — currently failing: `centersToEdges(undefined)` because `beliefGridFromFlat` still reads `tau_grid`.
- Density deposits lot mass from `f_marginals` row-major `L×K` → `projector.test.ts::… > deposits lot mass from f_marginals row-major L×K` — currently failing: same `tau_grid` undefined / `age_marginals` missing.
- `L=0` f-native boundary returns empty density → `projector.test.ts::… > returns empty density for L=0 f-native boundary` — **passing** (early return before τ access; implementer must keep).
- Heatmap axis labels “Freshness × count” → `projector.test.ts::… > exposes Freshness × count heatmap axis labels` — currently failing: `beliefHeatmapAxisLabels` export missing.
- Merged f marginal `m[k] = Σ_l lot_counts[l] × f_marginals[l×K+k]` → `projector.test.ts::fMarginalFromFlat (T-C2-A / AC-frontend) > merges per-lot f mass` — currently failing: `fMarginalFromFlat` export missing.

### AC-frontend — `inventoryTarget.ts` bands use `E[f]` from f-marginals (not τ-day Weibull)

- Belief-path effective inventory equals `Σ_l lot_counts_l × Σ_k f_marginal[l,k] × f_grid[k]`, not `survivalWeightedInventory` Weibull(τ) → `web/src/charts/inventoryTarget.test.ts::inventorySeries E[f] effective (T-C2-A / AC-frontend) > belief path: effective equals Σ lot_counts × E[f|lot], not Weibull(τ)` — currently failing: `inventorySeriesFromBelief` calls `expectedLotsFromFlat` which reads undefined `age_marginals`.
- `E[f]` boundary all mass at `f=0` → effective `0` → `inventoryTarget.test.ts::… > E[f] boundary: all mass at f=0 yields effective 0` — currently failing: same τ-field access error.
- `E[f]` boundary all mass at `f=1` → effective `Σ lot_counts` → `inventoryTarget.test.ts::… > E[f] boundary: all mass at f=1 yields effective Σ lot_counts` — currently failing: same.
- Freshness composition bands partition by `f_grid` thirds (`<1/3`, `[1/3,2/3)`, `≥2/3`), not τ-day 0–2 / 3–5 / 6+ buckets → `inventoryTarget.test.ts::freshness composition bands from f_marginals (T-C2-A / AC-frontend) > belief path: bands partition by f_grid thirds, not τ-day …` — currently failing: `ageCompositionSeriesFromBelief` → `expectedAgeBands` reads `age_marginals` / `tau_grid`.
- `f=1/3` lands in mid band (stale/fresh boundary) → `inventoryTarget.test.ts::… > f=1/3 lands in mid band` — currently failing: same τ-field access.

## Not covered by tests

- `cd web && npm test` full web suite green — verifier after implement lands all shards.
- `mock adapter` f-wire payloads — covered by other T-C2-A shards (`AC-python-wire` / session); frontend qa scope is projector + inventoryTarget only per concurrency plan.
- Chart pixel/DOM rendering of renamed axis text in `beliefAgeCount.ts` — projector label export is the unit seam; visual regression left to implement + manual studio check.
