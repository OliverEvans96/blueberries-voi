# C2 freshness accuracy study (rust)

**Source:** `outputs/c2_accuracy_study_rust.json`  
**Engine:** rust  
**Wall time:** 498.8 s  
**Simulation:** 14 days/rep, 15 units/lot, unit-level gamma truth  

## Verdict: 500 ms + accuracy under realistic conditions

**Realistic demo point:** N=200, L=4, K=8, 20 units/lot, 14-day rollouts.  **Runtime gate:** Rust `bench_c2_algorithms` (≤500 ms/day compute).  **Accuracy gate:** mean_f MAE and hist TV at L=4 vs best tractable option.

### Runtime (Rust timing, demo point)

| Algorithm | mean ms | vs 500 ms |
|-----------|--------:|:---------:|
| baseline (production filter_step) | 6.0 | PASS |
| A — unit-tag bootstrap PF | 6.9 | PASS |
| B — per-lot histogram PF | 24.0 | PASS |
| D — split C1/C2 (misspecified) | 1.0 | PASS |
| E — gamma-frailty collapse | 19.0 | PASS |

### Accuracy at L=4 (this study)

| Algorithm | mean_f MAE | hist TV | ESS |
|-----------|----------:|--------:|----:|
| baseline | 0.0000 | 0.0000 | 174 |
| c2_a | 0.0061 | 0.6787 | 200 |
| c2_b | 0.0324 | 0.0098 | 198 |
| c2_c | 0.2757 | 0.8670 | — |

### Ruled out

- **Joint exact-WOR LL (baseline totals, MF sweeps) at L>4** — exponential ∏(n+1) states; not runnable at L=20 (9.54e+13 states).
- **D (split filter)** — production filter fixed at L=2; does not track full shelf (misspecified for C2 freshness).
- **c2_c** — accuracy insufficient at L=4 (MAE=0.276, TV=0.867).
- **c2_b @ K=8** — histogram too coarse (MAE=0.132, TV=0.284); use K≥16.

### Viable under 500 ms + acceptable L=4 accuracy

- **B — per-lot histogram PF**, 24 ms
- **A — unit-tag bootstrap PF**, 7 ms
- **baseline (production filter_step)**, 6 ms
- **E — gamma-frailty collapse**

MAE tolerance: >0.040 (max(0.04, 2× best ref=0.006 among A/B)). Hist-TV gate for B: >0.15.

## L=20: what changes?

- **Exact joint lot-WOR LL** (baseline filter, MF with `log_p_sales_waste`): WOR states = ∏(n_l+1). At L=20, n=4/lot → **9.54e+13** — **not runnable**.
- At L=4, n=4: **625** states — tractable.
- **Histogram B** and **unit-tag A**: polynomial in L; **still viable at L=20**.
- **MF (C)** with exact LL in sweeps: **blocked at L=20** (same as baseline joint LL).
- With **L≤20 shelves**, production should use **per-lot histogram (B)** or **unit tags (A) + sales_by**, not one joint exact-WOR call over all lots.

## Metrics

- **mean_f MAE**: |E[f]_belief − E[f]_truth| averaged over lots
- **hist TV**: ½Σ|h − h_truth| per lot, averaged
- **ESS**: particle effective sample size (bootstrap only)
- **cov90**: fraction of lots where truth E[f] ∈ [p5, p95] of particles

## K sensitivity (L=4, N=200, totals)

| label | algo | mean_f MAE | hist TV | ESS | cov90 |
|-------|------|------------|---------|-----|-------|
| K=16 | c2_b | 0.0327 ± 0.0006 | 0.0126 ± 0.0046 | 198.6 | 0.00 |
| K=32 | c2_b | 0.0157 ± 0.0000 | 0.0014 ± 0.0005 | 200.0 | 0.00 |
| K=8 | c2_b | 0.1316 ± 0.0061 | 0.2844 ± 0.0219 | 149.7 | 0.00 |

## L sweep (N=200, K=16 for B; MF only L≤4)

| label | algo | mean_f MAE | hist TV | ESS | cov90 |
|-------|------|------------|---------|-----|-------|
| L=2 | baseline | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 156.6 | 1.00 |
| L=4 | baseline | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 174.1 | 1.00 |
| L=2 | c2_a | 0.0077 ± 0.0012 | 0.6966 ± 0.0293 | 200.0 | 1.00 |
| L=20 | c2_a | 0.0060 ± 0.0005 | 0.6224 ± 0.0168 | 200.0 | 1.00 |
| L=4 | c2_a | 0.0061 ± 0.0008 | 0.6787 ± 0.0186 | 200.0 | 1.00 |
| L=8 | c2_a | 0.0057 ± 0.0007 | 0.6452 ± 0.0283 | 200.0 | 1.00 |
| L=2 | c2_b | 0.0322 ± 0.0007 | 0.0082 ± 0.0058 | 199.5 | 0.00 |
| L=20 | c2_b | 0.0312 ± 0.0000 | 0.0002 ± 0.0002 | 200.0 | 0.00 |
| L=4 | c2_b | 0.0324 ± 0.0007 | 0.0098 ± 0.0044 | 198.5 | 0.00 |
| L=8 | c2_b | 0.0313 ± 0.0000 | 0.0000 ± 0.0000 | 200.0 | 0.00 |
| L=2 | c2_c | 0.4002 ± 0.0279 | 0.9701 ± 0.0104 | — | — |
| L=4 | c2_c | 0.2757 ± 0.0251 | 0.8670 ± 0.0202 | — | — |

## Particle count (L=4, K=16, B)

| label | algo | mean_f MAE | hist TV | ESS | cov90 |
|-------|------|------------|---------|-----|-------|
| N=200 | c2_b | 0.0340 ± 0.0011 | 0.0219 ± 0.0067 | 196.6 | 0.00 |
| N=2000 | c2_b | 0.0335 ± 0.0007 | 0.0187 ± 0.0046 | 1972.2 | 0.00 |

## Observation channel (L=4, N=200, K=16)

| label | algo | mean_f MAE | hist TV | ESS | cov90 |
|-------|------|------------|---------|-----|-------|
| sales_by | c2_a | 0.0016 ± 0.0002 | 0.5141 ± 0.0438 | 199.9 | 1.00 |
| totals | c2_a | 0.0071 ± 0.0013 | 0.6383 ± 0.0252 | 193.6 | 1.00 |
| sales_by | c2_b | 0.0313 ± 0.0000 | 0.0000 ± 0.0000 | 200.0 | 0.00 |
| totals | c2_b | 0.0325 ± 0.0005 | 0.0120 ± 0.0048 | 198.7 | 0.00 |

## K sensitivity takeaway (B)

- K=8: MAE=0.1316, TV=0.2844
- K=16: MAE=0.0327, TV=0.0126
- K=32: MAE=0.0157, TV=0.0014

## Observation channel takeaway

- **c2_b** / totals: MAE=0.0325, TV=0.0120, ESS=198.7
- **c2_a** / totals: MAE=0.0071, TV=0.6383, ESS=193.6
- **c2_b** / sales_by: MAE=0.0313, TV=0.0000, ESS=200.0
- **c2_a** / sales_by: MAE=0.0016, TV=0.5141, ESS=199.9

## Reproduce

```bash
cd .worktrees/timing-freshness
export OMP_NUM_THREADS=1
# Rust accuracy study
cargo run -p voi_core --release --bin bench_c2_accuracy -- --probe
cargo run -p voi_core --release --bin bench_c2_accuracy -- \
  --output outputs/c2_accuracy_study_rust.json
uv run python experiments/generate_c2_accuracy_report.py
```
