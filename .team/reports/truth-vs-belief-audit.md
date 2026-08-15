# Truth vs belief audit (studio)

**Run:** 2 (re-audit)  
**Date:** 2026-08-15  
**Branch / worktree:** `audit/truth-vs-belief-2026-08-15` @ `.worktrees/truth-belief-audit-2026-08-15`  
**Tip audited:** `558236e` (`main`)  
**Scope:** Backlog “Frontend truth vs belief audit” (ADR [0125](../adr/0125-studio-show-truth-js-only.md), T-115).  
**Method:** Three concurrent explore subagents + `npm test` in worktree.

**Run 1 baseline:** `406209e` → `0b874be` (first audit report + obs-scenario `patchEngineState` fix).

---

## Verdict

**Still substantially complete.** T-115 / ADR 0125 presentation contract holds on current `main`. No new default god-mode leaks. One medium wire gap from run 1 is **fixed** (`patchEngineState` + `onSetObsScenario`). Remaining items are polish, opt-in Rust backend, and deferred knowledge-scenario UI audit.

---

## Delta vs run 1

| Item | Run 1 | Run 2 @ `558236e` |
|------|-------|-------------------|
| `patchEngineState` updates last `belief_history` on scenario switch | **Gap** | **Fixed** (`projector.ts` ~370–384; tests in `projector.test.ts`) |
| `onSetObsScenario` wipes episode via `applySnapshot` | Risk | **Fixed** — uses `patchEngineState` (`main.ts` ~700–702; `studioWiring.test.ts`) |
| Vitest | 33 files / 255 passed | **34 files / 262 passed** (+`pnlTimeseries.test.ts`; unrelated to truth/belief) |
| PnL sparkline / focus chart | Daily bars | **Cumulative** lines (`558236e`) — observables only; no truth/belief impact |
| Default-off chart gating | Pass | **Pass** (unchanged) |
| Studio polish (`.lot` vs `.truth-*`, chip legend, axis bleed) | Open | **Open** (unchanged) |
| PyO3 / Rust policy parity | Open | **Open** (unchanged) |
| `main.ts` showTruth bootstrap integration test | Open | **Open** (partial: wiring test for obs-scenario only) |
| ADR 0125 status | PROPOSED | **PROPOSED** (human accept still pending) |

---

## ADR 0125 decision checklist

| # | Decision | Status | Evidence |
|---|----------|--------|----------|
| 1 | Keep `belief` + `live_lots` on wire; no `showTruth` on Snapshot/DayDelta | **PASS** | `session.py`; `projector.test.ts` |
| 2 | Default `showTruth = false` | **PASS** | `showTruth.ts`; vitest |
| 3 | JS-only presentation gate | **PASS** | No backend show-truth flag |
| 4 | `localStorage` + `studio--show-truth` on `#app` | **PASS** | `controls.ts`, `main.ts` |
| 5 | Rolling `belief_history` for inventory / age bands | **PASS** | `projector.ts`; delta + patch paths |
| 6 | Defer knowledge-scenario-specific chrome | **Deferred** | Backlog: *Frontend knowledge-scenario UI audit* |

---

## Chart / section matrix

**Legend:** **Obs** = manager-visible books. **Belief** = filter posterior. **Truth** = sim cohort geometry.

| Plot / area | Primary data | Gated when `showTruth=false`? | Notes |
|-------------|--------------|--------------------------------|-------|
| Units sold / missed / spoilage | Obs | — | Correct for manager mode |
| Lots · day × age (store) | Truth | **Yes** — `historyForCharts()` | Caption hints overlay |
| Belief heatmap (Play + Belief) | Belief | Markers **yes** (`truthLots()`) | Density always belief |
| Age marginal | Belief | — | |
| Sales vs demand | Obs | — | |
| Inventory vs base-stock | Belief *or* truth | **Yes** | Logistics + Controller |
| On-hand by age band | Belief *or* truth | **Yes** | |
| Survival + lot rug | Truth rug | **Yes** | |
| Arrival prior + receipt rug | Config + truth samples | **Yes** | Rug via `historyForCharts()` |
| PnL / sparkline | Obs (JS-reprojected) | — | Cumulative since `558236e`; still obs-only |

**Autopilot / policy:** engine `act()` on belief path — does not use truth overlays. **PASS.**

---

## Wire & backend

| Layer | Truth | Belief | Backend gating? |
|-------|-------|--------|-----------------|
| Python `EngineSession` | `live_lots`, thin `history` | `belief` flat buffer | No |
| JS projector | `live_lots`, `history[].lots` via `asDay` | `flatBelief`, `belief_history` | Presentation only |
| WASM | `live_lots` | `belief` | No |

### Wire deep dive

| Finding | Severity | Run 2 |
|---------|----------|-------|
| No backend `showTruth` gating | PASS | Unchanged |
| `patchEngineState` refreshes `belief_history` on scenario switch | PASS | **Fixed since run 1** |
| `onSetObsScenario` preserves client history | PASS | **Fixed since run 1** |
| `applySnapshot` clones one belief for all history days | Medium (mock reload) | Unchanged |
| `vm.on_hand` / `effective_inv` from `liveLots` only | Low | Unchanged |
| Mock `generateFlatBelief` from truth lots | Known mock limit | Unchanged |
| PyO3 empty `live_lots` / stub belief | Medium (opt-in rust) | Unchanged |
| Rust `act_rollout` from true counts | Medium (opt-in rust) | Unchanged |
| `beliefGridFromFlat(flat, liveLots)` axis extent bleed | Low | Unchanged |

---

## Test coverage (ADR 0125)

**Worktree run:** `cd web && npm test` → **34 files / 262 passed** (2026-08-15).

| Criterion | Automated | Location |
|-----------|-----------|----------|
| Default off + localStorage | Yes | `showTruth.test.ts` |
| Toggle UX + `studio--show-truth` | Yes | `showTruthUi.test.ts`, `controls.showTruth.test.ts` |
| Wire omits `showTruth` | Yes | `projector.test.ts` |
| `belief_history` tracks `history` | Yes | `projector.test.ts` |
| `patchEngineState` belief trail + history preserved | Yes | **New** — `projector.test.ts` (since `0b874be`) |
| `onSetObsScenario` uses `patchEngineState` | Yes | **New** — `studioWiring.test.ts` (since `0b874be`) |
| Per-chart overlay gating | Yes | Chart module tests |
| Inventory / age belief helpers | Yes | `inventoryTarget.test.ts` |
| `main.ts` showTruth bootstrap / chart branches | **No** | Still open |
| Persisted `"true"` on full app remount | **No** | Storage round-trip only |

---

## Open gaps (unchanged unless noted)

### Medium — opt-in Rust / mock

1. PyO3 wire stubs (`crates/voi_py/src/lib.rs`)
2. Rust `act_rollout` policy from truth counts (`voi_core/session.rs`)
3. `applySnapshot` belief_history on mock multi-day reload

### Low — UX polish

4. Store history `.lot` fill vs `.truth-*` overlay language (`history.ts`)
5. `.chip-lots` legend visible when chart empty (`main.ts` ~109)
6. Belief heatmap count axis from truth `n` (`projector.ts` ~419)
7. `vm.on_hand` / `effective_inv` always truth-derived (latent)

### Deferred

8. **Frontend knowledge-scenario UI audit** (substantive remainder)
9. **Frontend controls/plots audit**

### Optional

10. `main.ts` showTruth end-to-end integration test
11. Studio truth polish bundle (items 4–6)

---

## Recommended actions

- Human accept ADR 0125 (`PROPOSED` → `ACCEPTED`).
- Proceed with **Frontend knowledge-scenario UI audit** as the substantive follow-on.
- Optional: T-110 rust wire/policy parity; studio polish bundle; `main.ts` integration test.

---

## Subagent runs

| Run | Agent | Focus |
|-----|-------|-------|
| 1 | [Audit web charts](84ed31d0-3071-429c-9f13-33bcdee3e1d3) | Chart matrix, polish |
| 1 | [Audit wire protocol](6d0bd60a-52c9-48ad-b508-6387a173d486) | Wire/backend |
| 1 | [Audit tests ADR](2c8c0908-c8ed-4e57-93bd-2da7661a77e6) | AC→tests |
| 2 | [Audit web charts](0932536a-3cb6-4d23-992f-742b42fb9dc0) | Re-audit @ `558236e` |
| 2 | [Audit wire protocol](8a0a69a6-ca9e-4012-ac34-575cc4f1bf8a) | Re-audit @ `558236e` |
| 2 | [Audit tests ADR](5b2f4c4d-b346-41bf-8719-8da8408379d7) | Re-audit @ `558236e` |
