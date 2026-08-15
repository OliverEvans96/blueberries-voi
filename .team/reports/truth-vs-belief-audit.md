# Truth vs belief audit (studio)

**Date:** 2026-08-15  
**Scope:** Backlog item “Frontend truth vs belief audit” (ADR [0125](../adr/0125-studio-show-truth-js-only.md), T-115).  
**Method:** Three concurrent explore subagents (web charts, wire/backend, tests/docs) plus spot-check on `main` @ `406209e`.

## Verdict

**Substantially complete on `main`.** T-115 landed (merge `3ddfd69`); the studio defaults to manager belief presentation and gates sim-truth overlays behind **Sim truth overlay** (`showTruth`, ADR 0125). The original audit goal is met for V1.

Remaining work is **polish and deferred scope**, not a missing core feature.

---

## ADR 0125 decision checklist

| # | Decision | Status | Evidence |
|---|----------|--------|----------|
| 1 | Keep `belief` + `live_lots` on wire; no `showTruth` on Snapshot/DayDelta | **PASS** | `session.py` `_snapshot` / `build_day_delta`; `projector.test.ts` omits `showTruth` on payloads |
| 2 | Default `showTruth = false` | **PASS** | `showTruth.ts` `loadShowTruth()`; vitest |
| 3 | JS-only presentation gate | **PASS** | No Python/Rust/WASM show-truth flag |
| 4 | `localStorage` + `studio--show-truth` on `#app` | **PASS** | `showTruth.ts`, `controls.ts`, `main.ts` |
| 5 | Rolling `belief_history` for inventory / age bands | **PASS** | `projector.ts` append on delta; `inventoryTarget.ts` belief series |
| 6 | Defer knowledge-scenario-specific chrome | **Deferred** | Backlog: *Frontend knowledge-scenario UI audit* |

---

## Chart / section matrix

**Legend:** **Obs** = manager-visible books (sales, demand, orders, PnL). **Belief** = filter posterior. **Truth** = sim cohort geometry (`live_lots`, `history[].lots`, `age_at_receipt`).

| Plot / area | Primary data | Gated when `showTruth=false`? | Notes |
|-------------|--------------|--------------------------------|-------|
| Units sold | Obs | — | Correct for manager mode |
| Missed sales | Obs (`stockout`) | — | T-116 |
| Lots · day × age (store) | Truth | **Yes** — `historyForCharts()` strips `lots` + `age_at_receipt` | Caption hints overlay (`main.ts`) |
| Spoilage | Obs | — | |
| Belief heatmap (Play + Belief) | Belief | Markers **yes** (`truthLots()`) | Density always belief |
| Age marginal | Belief | — | |
| Sales vs demand | Obs | — | |
| Inventory vs base-stock | Belief *or* truth | **Yes** — `inventorySeriesFromBelief` vs `inventorySeries` | Logistics + Controller |
| On-hand by age band | Belief *or* truth | **Yes** — `ageCompositionSeriesFromBelief` | |
| Survival + lot rug | Truth rug | **Yes** — `truthLots()` | Prior curve is config |
| Arrival-age prior + receipt rug | Config + truth samples | **Yes** — rug uses `historyForCharts()` | |
| Arrival ΔT shift | Config | — | No truth |
| Controller orders | Obs | — | |
| PnL / sparkline | Obs (JS-reprojected) | — | |

**Autopilot / policy:** uses engine `act()` on belief path only — does not consume truth overlays. **PASS.**

---

## Wire & backend

| Layer | Truth fields | Belief fields | Gating on backend? |
|-------|--------------|---------------|-------------------|
| Python `EngineSession` | `live_lots`, thin `history` (no lots on HTTP path) | `belief` flat buffer | No |
| JS projector | mirrors `live_lots`, fills `history[].lots` from delta | `flatBelief`, `belief_history` | Presentation only |
| WASM stub | `live_lots` | `belief` | No |

Belief export uses `current_belief_flat` / RBPF — not conflated with cohort truth. **PASS.**

Minor note: `beliefGridFromFlat(flat, liveLots)` always extends the count axis using truth `n` (`projector.ts` ~419). This affects axis extent only, not drawn truth geometry.

### Wire-protocol deep dive ([Audit wire protocol truth/belief](6d0bd60a-52c9-48ad-b508-6387a173d486))

| Finding | Severity | Notes |
|---------|----------|-------|
| No backend `showTruth` gating | **PASS** | ADR 0125 compliant |
| Python `EngineSession` separates `belief` / `live_lots` | **PASS** | `session.py` `_snapshot` / `build_day_delta` |
| `patchEngineState` refreshes last `belief_history` entry on scenario switch | **PASS** | `projector.ts` ~370–384 (partial fix already on `main`) |
| `applySnapshot` clones **one** `snapshot.belief` for every history day | **Medium (mock / reload)** | Wire has no per-day belief on Snapshot; Python reset sends `history: []` so live path OK; mock `toSnapshot()` can send multi-day history with single belief → wrong manager-mode inventory/age bands until more deltas |
| `vm.on_hand` / `effective_inv` always from `liveLots` | **Low** | Not in play chrome today; ADR 0125 consequence if surfaced |
| Mock `generateFlatBelief` uses truth `n` / blurred truth `τ` | **Known mock limitation** | Acceptable for fake physics; not a filter posterior |
| PyO3 `py_delta` / `py_snapshot` emit empty `live_lots` + empty belief | **Medium (opt-in rust backend)** | `crates/voi_py/src/lib.rs`; `_coerce_day_delta` fallback when mapping incomplete; studio default is Python/WASM not PyO3 |
| Rust `act_rollout` orders from true `counts`/`taus` | **Medium (opt-in rust backend)** | `voi_core/session.rs`; Python path uses `shelf_belief_from_rbpf` — policy parity gap |
| `vm.history` internally holds truth lots (via `asDay` fallback) | **Low** | Render path strips via `historyForCharts()`; direct VM consumers could leak god-mode |
| Wire `day.L` = on-hand count vs `belief.L` = lot slots | **Doc / naming** | Easy to misread in fixtures |

---

## Test coverage (ADR 0125)

Mapping from [Audit tests ADR contracts](2c8c0908-c8ed-4e57-93bd-2da7661a77e6). Vitest on `main`: **33 files / 255 passed** (includes all T-115 suites). Verify snapshot in `T-115.md` cites 26/201 at verify tip — counts drifted as later web tests landed.

| Criterion | Automated | Location |
|-----------|-----------|----------|
| Default off + localStorage round-trip | Yes | `showTruth.test.ts` |
| Toggle UX + `studio--show-truth` class | Yes | `showTruthUi.test.ts`, `controls.showTruth.test.ts` |
| Wire payloads omit `showTruth` | Yes | `projector.test.ts` |
| `belief_history` tracks `history` | Yes | `projector.test.ts` |
| Belief density independent of `live_lots` patch | Yes | `projector.test.ts` |
| Per-chart overlay gating (empty lots → zero nodes) | Yes | `beliefAgeCount`, `survival`, `history`, `arrivalPrior` tests |
| Inventory / age belief vs truth series helpers | Yes | `inventoryTarget.test.ts` |
| Belief blurb off-mode (no required “truth”) | Yes | `sections.belief.test.ts` |
| `main.ts` bootstrap + `renderActiveFocusPlots` branches | **No** | Acknowledged in `T-115-tests.md`; `studioWiring.test.ts` has no showTruth coverage |
| Persisted `"true"` on full app remount | **No** | Storage round-trip only |

All show-truth vitest files pass (`npm test -- --run showTruth`).

---

## Studio presentation polish ([Audit web charts truth/belief](84ed31d0-3071-429c-9f13-33bcdee3e1d3))

No default god-mode leak found. Remaining UX consistency items:

| Item | Severity | Refs |
|------|----------|------|
| Store history uses `.lot` green fill, not ADR 0125 `.truth-circle`/`.truth-cross` language | Low | `history.ts`; belief/survival use `.truth-*` |
| `.chip-lots` legend always visible while lots chart empty when off | Low | `main.ts` legend; caption updated in `syncTruthCaptions` |
| `beliefGridFromFlat(..., liveLots)` extends count axis from truth even when overlay off | Low | `projector.ts` ~419 — axis geometry only |
| Play lots scatter + belief heatmap both show truth when on (redundant surfaces) | Low | `sections.ts` Play plotIds; not a default leak |
| `main.ts` integration guard for toggle branches | Optional test | See test table above |

---

## Gaps (ordered by severity)

### Medium — opt-in Rust / mock paths (not T-115 studio default)

1. **PyO3 wire stubs** — `py_delta` / `py_snapshot` in `crates/voi_py/src/lib.rs` emit empty `live_lots` and empty belief; `_coerce_day_delta` in `session.py` fills stubs when Rust returns non-Mapping. Affects `BLUEBERRIES_VOI_BACKEND=rust` only (T-110).
2. **Rust `act_rollout` policy** — `voi_core/session.rs` orders from true cohort counts; Python uses RBPF belief export. Policy parity gap on rust backend.
3. **`applySnapshot` belief_history** — clones current `snapshot.belief` for all history days; harmless on Python reset (`history: []`) but wrong for mock mid-episode reload with multi-day history until deltas replay.

### Low — document / backlog hygiene

4. **ADR 0125 status** still `PROPOSED`; implementation verified — human should accept.

### Low — UX polish (studio presentation)

5. **Truth visual language split** — store history `.lot` fill vs belief/survival `.truth-*` overlays ([web charts audit](84ed31d0-3071-429c-9f13-33bcdee3e1d3)).
6. **Lots chip legend** (`.chip-lots`) always visible; only styled when `studio--show-truth`. Chart empty when off.
7. **Belief heatmap count axis** — `beliefGridFromFlat(flat, liveLots)` always sizes axis from truth `n` (`projector.ts` ~419); overlay dots gated but axis may reflect god-mode extent.
8. **`vm.on_hand` / `vm.effective_inv`** always from `liveLots` (`projector.ts` ~440–441). Not in play chrome today.

### Deferred (explicit in ADR 0125)

9. **Knowledge-scenario UI audit** — substantive remainder of “Frontend truth vs belief audit”; e.g. F2 receipt ages as “observed” vs hidden-state ([tests audit](2c8c0908-c8ed-4e57-93bd-2da7661a77e6)).
10. **Frontend controls/plots audit** — separate backlog item (redundant controls / plot relevance).

### Optional follow-on (no ticket id yet)

11. **`main.ts` showTruth integration test** — bootstrap default-off + chart branch wiring (`studioWiring.test.ts` or dedicated file).
12. **Studio truth polish bundle** — unify history `.truth-*` styling; gate belief grid count axis; hide/dim `.chip-lots` when overlay off.

---

## Recommended backlog updates

- **T-115 / truth-vs-belief V1** — landed on `main`; substantive audit thread closed except knowledge-scenario UI audit.
- **ADR 0125** — human accept (`PROPOSED` → `ACCEPTED`).
- **Rust backend wire + policy parity** — T-110 follow-on (see wire deep dive).
- **Optional studio polish** — truth visual language, belief grid axis gate, chip legend, `main.ts` integration test (audit items 11–12).
- Keep **Frontend knowledge-scenario UI audit** and **Frontend controls/plots audit** as active follow-ons.

---

## Subagent notes

| Agent | Focus |
|-------|-------|
| [Audit web charts truth/belief](84ed31d0-3071-429c-9f13-33bcdee3e1d3) | Chart matrix, presentation polish gaps |
| [Audit wire protocol truth/belief](6d0bd60a-52c9-48ad-b508-6387a173d486) | Wire/backend separation, Rust/mock gaps |
| [Audit tests ADR contracts](2c8c0908-c8ed-4e57-93bd-2da7661a77e6) | AC→test map, stale `.team/` artifacts, verdict |

Studio default path (Python session / WASM) is ADR 0125 compliant for presentation gating.
