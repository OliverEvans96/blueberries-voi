# T-163 Phase 2 — Critical evaluation

**Date:** 2026-08-27  
**Base:** post-Phase-1 `team/arrival-breaks/integrate` tip (PR #72 freshness calibration)  
**Authority:** `.team/specs/T-163.md`, `.team/plans/arrival-transit-generative-v2.md`, PR #65 goals

---

## Executive summary

Stage 1 (v2 generative transit) and Stage 2 (multilot L=3) are **largely implemented** on integrate with Phase 1 freshness fixes merged. Fast CI and PR #71 thermal cache meet sub-15min gate goals. One **known contract gap** remains: S1.8 ladder MAE ordering ratio ≈ 1.07 vs required ≥ 3.0 — explicitly not weakened.

Phase 3 (notebook pipeline: split nb 12, damped_sw only, nb 17/19) can start once PR #72 is merged to remote integrate.

---

## Stage 1 — Transit generative v2

| AC | Status | Notes |
|----|--------|-------|
| S1.1 Abdella duration marginal | **pass** | `t163_v2_calibration` / gamma sum law |
| S1.2 Var(log d) | **pass** | within ±0.02 of 0.205 at ρ=0 |
| S1.3 Clean-chain φ̄ moments | **pass** | tuned nominal μ_k / σ_hour |
| S1.4 Hourly OU on path | **pass** | `rho_zero_trace_has_hourly_ou_variation` |
| S1.5 Break pulses | **pass** | default ρ > 0 reaches T_break |
| S1.6 Trace ↔ integrator parity | **pass** | ≥40 seeded draws |
| S1.7 Filter coherence | **pass** | `t163_v2_filter_coherence` |
| S1.8 Ladder ordering | **gap** | MAE(P0)/MAE(F2) ≈ **1.07** at n=20; guard requires ≥ 3.0 — **not relaxed** |
| S1.9 Artifact schema | **pass** | v2 fields present; mu_T/sigma_T/temp_floor_c retired |
| S1.10 Fit script honesty | **pass** | duration gamma only; provenance documented |
| S1.11 Unified corridor | **pass** | abdella_all only; no short/long haul chips |
| S1.12 Per-day runtime | **pass** | ~5.7 ms/day @ N=200 (bench_day_timing) |
| S1.13 Design variance share | **pass** | arrival_calibration_note.py metric |
| S1.14 Breaks inside calendar d | **pass** | breaks within d, not additive |
| S1.15 UPC mixture law | **pass** | mixture_law tests |
| S1.16 Guard supersession | **pass** | withdrawn deterministic-baseline tests replaced |

---

## Stage 2 — Multi-lot L=3

| AC | Status | Notes |
|----|--------|-------|
| S2.1 Three lot ids | **pass** | session smoke: n_lots=3 |
| S2.2 Exposure additivity | **pass** | upstream + shared per lot |
| S2.3 Per-lot traces | **pass** | temp_traces_by_lot wire |
| S2.4 Quantity split | **pass** | not multiplied |
| S2.5 LGTIN birth | **pass** | three segments |
| S2.6 UPC mixture birth | **pass** | pointwise CDF average |
| S2.7 Per-lot resolve | **pass** | resolve_arrival_f_law per lot |
| S2.8 FilterObs shape | **pass** | per-lot pack dates + traces |
| S2.9 unit_ll unchanged | **pass** | n_lots loops suffice |
| S2.10 Kernel tests | **pass** | t140/t141/t150 updated; multilot session tests `#[ignore]` slow tier |

---

## Stage 3 — Mirrors (deferred to PR #65 closeout)

Wire mirrors, studio version bump, citation guards — tracked in T-163 Stage 3 AC; not blocking Phase 2/3 notebook work.

---

## Phase 1 freshness calibration (PR #72)

| Metric | Pre-calibration | Post-Phase-1 | Target |
|--------|-----------------|--------------|--------|
| Arrival f p50 | mass < 0.5 | **0.745** | ≥ 0.65 |
| Session delivery mean_f | biased / low | **0.670** | ≥ 0.55 |
| Prior vs multilot truth bias | upward systematic | **≤ 0.03** | ≤ 0.03 |
| pct f < 0.5 | high | **4.8%** | realistic band |
| reference_life_days | 14 (collapsed by sync_params) | **26** | decoupled from eta_ref |

**User-reported pessimism/bias:** addressed on multilot path. Single-lot `t163_f_diag` still shows Prior sample bias ≈ −0.05 — misleading for AC; multilot test `prior_mean_f_matches_generative_multilot` is the binding check.

---

## Test tiering + PR #71 thermal cache vs sub-15min gate

- **Fast CI:** python `-m "not slow and not docs"` without coverage; rust ~6–8 min post thermal cache.
- **Slow tier:** multilot session stepping, ladder MC guards `#[ignore]` — nightly only (user cancelled full nightly for this pass).
- **Thermal cache (PR #71):** CDF + thermal_nodes built once at `ArrivalModel::embedded()` — init no longer pathological; session init < 30s in validation notebook.

Aligns with sub-15min PR gate goals.

---

## Risks / open issues

1. **S1.8 ladder MAE ratio ~1.07** — richest→least-informed ordering exists but ratio below 3×; needs separate tuning ticket; guard not weakened.
2. **VOI CRN baseline drift** — all scenarios now 246.0 profit (was differentiated 270.5/262.0/230.5); reflects fresher arrivals changing economics uniformly at this CRN fixture.
3. **Multilot slow tests ignored** — S2 AC covered by fast smoke + ignored full session tests; nightly tier validates end-to-end.
4. **PR #72 merge blocked** — coordinator hook blocked `gh pr merge`; human merge required when CI green.
5. **Stage 3 mirrors** — wire parity + studio version bump still open on integrate.

---

## Phase 3 readiness

**Yes**, Phase 3 (notebook pipeline: split nb 12, damped_sw only, nb 17/19) can start from post-Phase-1 integrate tip once PR #72 lands on remote integrate.
