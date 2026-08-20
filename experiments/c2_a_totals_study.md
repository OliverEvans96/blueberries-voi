# C2 Algorithm A + P1 totals deep study

**Source:** `outputs/c2_a_totals_study.json`  
**Bench:** `bench_c2_a_totals_study` (Rust / voi_core, production `filter_step_unit`)  
**Wall time:** 6.2 s  
**Setup:** N=200 particles, 15 units/lot, 14-day rollouts, totals-only observations (sales_total + waste_total), full P1 likelihood via production `unit_ll` + `unit_pf`

Cross-reference: [c2_accuracy_study_rust.md](c2_accuracy_study_rust.md) for multi-algorithm comparison at L≤20.

## Executive summary

| Gate | Result |
|------|--------|
| **Runtime @ L=20** | **5.7 ms/day** (p95 6.1 ms) — **PASS** vs 500 ms budget |
| **mean_f MAE @ L=20** | **0.0000** — excellent lot-mean freshness tracking |
| **Order qty match** | **100%** across all L and K — controller usable |
| **hist TV (particle mean)** | **~0.50–0.50** — high but *structural* (see TV vs mean) |
| **hist TV (belief wire @ K=8)** | **0.00–0.07** — coarser than particle TV at small L |

**Verdict:** C2-A with production `unit_pf` on P1 totals is **fast enough and accurate enough** for production controller use at L=20. Raw histogram TV is a **misleading** visualization metric for Algorithm A; prefer **mean_f** and **belief-wire** summaries for studio dashboards.

---

## Timing (production `filter_step_unit`, N=200)

| L | units | mean ms | p95 ms | vs 500 ms |
|---|------:|--------:|-------:|:---------:|
| 4 | 60 | 1.7 | 1.9 | PASS |
| 8 | 120 | 2.7 | 2.9 | PASS |
| 12 | 180 | 3.8 | 4.0 | PASS |
| 16 | 240 | 4.7 | 5.2 | PASS |
| 20 | 300 | **5.7** | **6.1** | **PASS** |

Timing scales roughly linearly in total units (L × 15). Production `filter_step_unit` (gamma aging + P1 LL + systematic resample) runs **~87× headroom** under the 500 ms gate at L=20.

---

## Accuracy (K_wire=8, studio default)

12 reps per L; scoring aligned with `bench_c2_accuracy.rs` `run_unit_pf`:

- **truth mean_f** = `lot_mean_f` over **all unit slots** (dead slots contribute f=0)
- **pred mean_f** = alive-only mean per lot, averaged over particles
- **truth hist** = histogram over **all units** per lot
- **pred hist** = alive-only histogram per lot, averaged over particles
- **tau** = `lot_tau_from_units` (alive-only mean_f → τ = (1−f)·η_ref) for both truth and pred
- Per-particle path RNG for sales kernel: `seed + p + day`

| L | mean_f MAE | hist_tv_particle | hist_tv_wire | tau_lot MAE | eff_inv rel err | order match | rank ρ | ESS_final | cov90 |
|--:|----------:|-----------------:|-------------:|------------:|----------------:|------------:|-------:|----------:|------:|
| 4 | 0.0000 | 0.500 | 0.000 | 0.0000 | 0.000 | 1.00 | 0.00 | 200 | 1.00 |
| 8 | 5.83e-06 | 0.500 | 0.073 | 0.1446 | 0.083 | 1.00 | 0.00 | 200 | 0.99 |
| 12 | 9.27e-05 | 0.500 | 0.073 | 0.0777 | 0.083 | 1.00 | 0.00 | 200 | 0.99 |
| 16 | 3.01e-05 | 0.500 | 0.073 | 0.0698 | 0.083 | 1.00 | 0.00 | 200 | 0.99 |
| 20 | 0.0000 | 0.500 | 0.000 | 0.0000 | 0.000 | 1.00 | 0.00 | 200 | 1.00 |

Standard errors (12 reps): mean_f MAE SE ≈ 0.0001; hist_tv_wire SE ≈ 0.07.

### Comparison with prior inline-bench study (pre–unit_pf promotion)

Prior `experiments/c2_a_totals_study.md` used an inline LL + multinomial resample loop. After wiring to production `filter_step_unit`:

| Metric @ L=20 | Inline bench | Production `unit_pf` |
|---------------|-------------:|-------------------:|
| mean ms/day | 11.6 | **5.7** |
| mean_f MAE | 0.0014 | **0.0000** |
| hist TV (particle) | 0.515 | **0.500** |
| ESS_final | 92 | **200** |

Production path is faster (systematic resample, shared `apply_gamma_aging`) and tracks lot-mean freshness with near-zero MAE on scripted seeds.

---

## K sensitivity @ L=20

| K | mean_f MAE | hist_tv_particle | hist_tv_wire | tau_lot MAE | eff_inv rel err | order match | ESS_final |
|--:|----------:|-----------------:|-------------:|------------:|----------------:|------------:|----------:|
| 4 | 0.0000 | 0.500 | 0.000 | 0.0000 | 0.000 | 1.00 | 200 |
| 8 | 3.44e-05 | 0.500 | 0.073 | 0.0511 | 0.083 | 1.00 | 200 |
| 16 | 4.86e-05 | 0.500 | 0.234 | 0.1648 | 0.250 | 1.00 | 200 |
| 32 | 1.17e-06 | 0.500 | 0.081 | 0.0581 | 0.083 | 1.00 | 200 |

**Takeaway:** K=8 (studio default) is a reasonable wire resolution. Particle-mean hist TV stays at the structural floor (~0.50) independent of K because scoring uses K=32 freshness bins independent of wire K.

---

## TV vs mean: controller and visualization

### What Algorithm A actually tracks

- **State:** per-unit freshness f on every slot (alive and dead).
- **Derived τ:** τ = (1−f)·η_ref at unit level; lot τ from alive-only mean_f (`lot_tau_from_units`).
- **Wire format** (`belief_flat`): `lot_counts` + **τ-binned** `age_marginals` at K — τ is not eliminated from the API.

### Why hist_tv_particle_mean ≈ 0.5 despite good mean_f

1. **Pred histogram** counts only **alive** units (renormalized).
2. **Truth histogram** counts **all 15 slots** including dead (f=0 → bin 0).
3. When most slots are dead, truth mass piles in bin 0; pred spreads mass over alive bins → TV ≈ 0.5 even when alive-only mean_f matches well.

This is **not** a filter failure; it is a **metric definition** issue. Do not use raw particle-mean hist TV as a pass/fail gate for Algorithm A.

### hist_tv_belief_wire vs hist_tv_particle_mean

| Metric | What it measures | Typical value @ L=20, K=8 |
|--------|------------------|---------------------------|
| hist_tv_particle_mean | K=32 freshness bins; alive-only pred vs all-slot truth | ~0.50 |
| hist_tv_belief_wire | Studio K=8 τ-bins on ESS-averaged wire belief | ~0.07 |

Wire TV uses τ-binned marginals (what the controller/studio consume), not raw f-bins. Both can be high while:

- **mean_f MAE < 0.002** (excellent; this run: 0.0000)
- **order_qty_match = 100%** (damped SW order from belief matches truth order)
- **coverage90_mean_f ≈ 99%** (this run: 1.00)

### Recommendation

| Use case | Preferred signal |
|----------|------------------|
| **Controller** (eff inventory, ordering) | mean_f / τ summaries via `effective_inventory_belief`, `damped_sw_order_belief` |
| **Studio viz** | belief wire `age_marginals` @ K=8; show mean_f or τ lot cards, not raw hist TV |
| **Regression testing** | mean_f MAE, order_qty_match, eff_inv_rel_err |
| **Avoid as primary gate** | hist_tv_particle_mean, hist_tv_belief_wire for Algorithm A |

Histogram PF (Algorithm B) is the right choice when **shape fidelity** (low hist TV) matters; Algorithm A wins on **mean freshness** and **runtime** under totals-only observations.

---

## Implementation notes (T-136 / ADR 0135 re-baseline)

Production `filter_step_unit` now uses **deterministic** P1 sales weights (feasibility +
binomial waste only) and **unscored** pooled WOR state removal after a finite likelihood
(ADR 0135). The legacy `bench_c2_a_totals_study` binary was removed (T-TAU-RETIRE); the
scripted gate `unit_pf_l20_scripted_mean_f_mae_and_order_match` in `unit_pf_ac.rs` remains
the regression anchor for P1 mean_f MAE and order match.

**Post-0135 expectations:** mean_f MAE and order match remain under existing thresholds;
timing is unchanged in order (O(L) multinomial term for F1 only). Headline figures in the
tables above are **pre-0135** provenance cited by ADR 0130 — re-run a full timing sweep
when the bench binary is restored or replaced.

- **Filter path:** `filter_step_unit` → `apply_gamma_aging` + obs router + unscored WOR removal + `systematic_resample`.
- **P1 likelihood (ADR 0135):** feasibility gate + `binom_pmf(waste, rem, p_die)` only — no MC path in the weight.
- **F1 likelihood (ADR 0135):** per-lot feasibility + multinomial cross-lot split from pooled `picking_weights_f` lot shares.
- **Bench:** legacy `bench_c2_a_totals_study` removed; use `unit_pf_l20_scripted_mean_f_mae_and_order_match` until restored.

---

## Reproduce

```bash
export OMP_NUM_THREADS=1
cargo run -p voi_core --release --bin bench_c2_a_totals_study -- --probe
cargo run -p voi_core --release --bin bench_c2_a_totals_study
uv run python experiments/generate_c2_a_totals_report.py
```

Outputs: `outputs/c2_a_totals_study.json`, this report.
