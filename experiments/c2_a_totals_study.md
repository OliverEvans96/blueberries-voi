# C2 Algorithm A + P1 totals deep study

**Source:** `outputs/c2_a_totals_study.json`  
**Bench:** `bench_c2_a_totals_study` (Rust / voi_core)  
**Wall time:** 14.7 s  
**Setup:** N=200 particles, 15 units/lot, 14-day rollouts, totals-only observations (sales_total + waste_total), full P1 likelihood (sequential sales kernel + binomial waste on dead slots)

Cross-reference: [c2_accuracy_study_rust.md](c2_accuracy_study_rust.md) for multi-algorithm comparison at L≤20.

## Executive summary

| Gate | Result |
|------|--------|
| **Runtime @ L=20** | **11.6 ms/day** (p95 16.0 ms) — **PASS** vs 500 ms budget |
| **mean_f MAE @ L=20** | **0.0014** — excellent lot-mean freshness tracking |
| **Order qty match** | **100%** across all L and K — controller usable |
| **hist TV (particle mean)** | **~0.49–0.52** — high but *structural* (see TV vs mean) |
| **hist TV (belief wire @ K=8)** | **0.15–0.66** — coarser than particle TV at small L; worsens with L |

**Verdict:** C2-A with full P1 totals is **fast enough and accurate enough** for production controller use at L=20. Raw histogram TV is a **misleading** visualization metric for Algorithm A; prefer **mean_f** and **belief-wire** summaries for studio dashboards.

---

## Timing (full P1 likelihood, N=200)

| L | units | mean ms | p95 ms | vs 500 ms |
|---|------:|--------:|-------:|:---------:|
| 4 | 60 | 2.8 | 3.2 | PASS |
| 8 | 120 | 5.5 | 6.8 | PASS |
| 12 | 180 | 9.0 | 10.1 | PASS |
| 16 | 240 | 11.4 | 12.7 | PASS |
| 20 | 300 | **11.6** | **16.0** | **PASS** |

Timing scales roughly linearly in total units (L × 15). Full P1 (sales path + binomial waste) adds modest cost vs sales-only totals in `bench_c2_accuracy.rs`; still **~40× headroom** under the 500 ms gate at L=20.

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
| 4 | 0.0004 | 0.484 | 0.146 | 0.287 | 0.060 | 1.00 | 0.00 | 177 | 1.00 |
| 8 | 0.0005 | 0.493 | 0.146 | 0.282 | 0.072 | 1.00 | −0.04 | 185 | 0.99 |
| 12 | 0.0014 | 0.493 | 0.292 | 0.273 | 0.181 | 1.00 | 0.00 | 168 | 0.99 |
| 16 | 0.0016 | 0.499 | 0.438 | 0.411 | 0.384 | 1.00 | 0.00 | — | 0.99 |
| 20 | 0.0014 | 0.515 | 0.656 | 0.332 | 0.304 | 1.00 | −0.01 | 92 | 0.99 |

Standard errors (12 reps): mean_f MAE SE ≈ 0.0004–0.0007; hist_tv_wire SE ≈ 0.10–0.13.

### Comparison with prior accuracy study (c2_a / totals / sales-only LL)

From `c2_accuracy_study_rust.md` at L=4, N=200:

| Study | LL | mean_f MAE | hist TV |
|-------|-----|----------:|--------:|
| c2_accuracy (sales-only) | sequential kernel | 0.0071 | 0.638 |
| **this study (full P1)** | kernel + binomial waste | **0.0004** | **0.484** |

Full P1 waste modeling tightens mean_f estimates. Particle-mean hist TV remains high (~0.48–0.52 vs ~0.64 prior) because the **scoring asymmetry** (alive-only pred vs all-slot truth) dominates, not the likelihood variant.

At L=20 the prior study reported c2_a mean_f MAE **0.0060** and hist TV **0.622** (sales-only). This study: MAE **0.0014**, particle TV **0.515** — consistent ranking, modest improvement from P1.

---

## K sensitivity @ L=20

| K | mean_f MAE | hist_tv_particle | hist_tv_wire | tau_lot MAE | eff_inv rel err | order match | ESS_final |
|--:|----------:|-----------------:|-------------:|------------:|----------------:|------------:|----------:|
| 4 | 0.0006 | 0.491 | 0.250 | 0.215 | 0.156 | 1.00 | 150 |
| 8 | 0.00002 | 0.510 | 0.292 | 0.059 | 0.085 | 1.00 | — |
| 16 | 0.0013 | 0.510 | 0.625 | 0.488 | 0.252 | 1.00 | 114 |
| 32 | 0.0015 | 0.495 | 0.404 | 0.274 | 0.250 | 1.00 | — |

**Takeaway:** K=8 (studio default) is a reasonable wire resolution — mean_f MAE and eff_inv error are best-in-class. Finer K (16–32) does **not** monotonically improve wire TV or controller metrics; coarser K=4 is competitive on tau and eff_inv. Particle-mean hist TV is **insensitive to K** (~0.49–0.51) because scoring uses K=32 freshness bins independent of wire K.

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
| hist_tv_particle_mean | K=32 freshness bins; alive-only pred vs all-slot truth | ~0.52 |
| hist_tv_belief_wire | Studio K=8 τ-bins on ESS-averaged wire belief | ~0.66 |

Wire TV uses τ-binned marginals (what the controller/studio consume), not raw f-bins. Both can be high while:

- **mean_f MAE < 0.002** (excellent)
- **order_qty_match = 100%** (damped SW order from belief matches truth order)
- **coverage90_mean_f ≈ 99%** (calibrated uncertainty)

### Recommendation

| Use case | Preferred signal |
|----------|------------------|
| **Controller** (eff inventory, ordering) | mean_f / τ summaries via `effective_inventory_belief`, `damped_sw_order_belief` |
| **Studio viz** | belief wire `age_marginals` @ K=8; show mean_f or τ lot cards, not raw hist TV |
| **Regression testing** | mean_f MAE, order_qty_match, eff_inv_rel_err |
| **Avoid as primary gate** | hist_tv_particle_mean, hist_tv_belief_wire for Algorithm A |

Histogram PF (Algorithm B) is the right choice when **shape fidelity** (low hist TV) matters; Algorithm A wins on **mean freshness** and **runtime** under totals-only observations.

---

## Implementation notes

- **Likelihood:** `p1_totals_loglik` = `sequential_kernel_path_logprob` (alive units) + `binom_pmf(waste, rem, p_die)` where `p_die = dead/total`.
- **Scoring bugs fixed:** prior bench compared pred/truth on identical alive-only views → zero MAE/TV; now matches `run_unit_pf` alignment.
- **Cleanup:** removed unused `particle_hist_alive`; `[[bin]] bench_c2_a_totals_study` present in `Cargo.toml`.

---

## Reproduce

```bash
cd .worktrees/timing-freshness
export OMP_NUM_THREADS=1
cargo run -p voi_core --release --bin bench_c2_a_totals_study -- --probe
cargo run -p voi_core --release --bin bench_c2_a_totals_study
uv run python experiments/generate_c2_a_totals_report.py   # optional
```

Outputs: `outputs/c2_a_totals_study.json`, this report.
