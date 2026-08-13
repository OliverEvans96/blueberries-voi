# M3 exact LL speedup bench (T-066)

**Date:** 2026-08-12  
**Status:** Measured on integrated tip (T-064 + T-065)  
**Math:** Exact ADR 0090 sequential-WOR density unchanged (no surrogate)  
**Env:** `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`

## Commits

| Role | SHA | Branch |
|------|-----|--------|
| Baseline (pre-change) | `f4a467f` | `main` |
| T-064 implement | `bf45fca` | `team/T-064/implement` |
| T-065 implement | `a79a9b1` | `team/T-065/implement` |
| Integration + report tip | `5666089` | `team/T-064-065/integrate` |

ADR: [0103](../adr/0103-exact-faster-p1-f2a-likelihood.md). Specs: T-064 / T-065 / T-066.

## How to reproduce

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  uv run python experiments/exact_ll_speedup_bench.py --label after \
  --out outputs/exact_ll_speedup_after.json
```

CRN probes (same protocol as brainstorm):

```bash
# β=2, seed=7, T=6 (burn=2 score=4), N=16, H=2, paths=1
uv run python -c "from blueberries_voi.voi.crn import run_voi_crn_cell; ..."
```

## 1. Isolated DP (`sequential_wor_composition_probs`)

Best of 3 after warmup. Speedup = baseline / after.

| counts | sales | baseline (ms) | after (ms) | speedup |
|--------|------:|--------------:|-----------:|--------:|
| [8,8] | 12 | 0.94 | 1.21 | 0.8× (tiny-state overhead) |
| [8,8,8] | 12 | 7.14 | 1.73 | **4.1×** |
| [12,12,12] | 18 | 25.6 | 2.78 | **9.2×** |
| [16,16,16] | 24 | 65.8 | 4.26 | **15.4×** |
| [20,20,20] | 30 | 146.5 | 6.51 | **22.5×** |

NumPy DP dominates at production-relevant state sizes; L=2 / small grids can be flat or slightly slower.

## 2. One `mean_field_update` (`max_sweeps=2`, K=8)

| counts | sales | baseline (s) | after (s) | speedup |
|--------|------:|-------------:|----------:|--------:|
| [8,8,8] | 12 | 0.617 | 0.263 | **2.3×** |
| [12,12,12] | 18 | 1.755 | 0.637 | **2.8×** |
| [16,16,16] | 24 | 3.626 | 1.169 | **3.1×** |

MF speedup is mostly the NumPy DP inside repeated LL calls (T-065). Unique-particle dedup (T-064) does not apply inside a single-particle MF microbench.

## 3. Closed-loop CRN (`run_voi_crn_cell`)

Protocol: β=2.0, seed=7, n_burn=2, n_score=4 (T=6), filter_n=16, H=2, n_rollout_paths=1.

| Scenario | baseline (s) | after (s) | speedup | per-day after |
|----------|-------------:|----------:|--------:|--------------:|
| **P1** | 327.6 | 30.7 | **10.7×** | 5.1 s |
| **F2a** | 759.1 | 100.1 | **7.6×** | 16.7 s |

Combined tip = **T-064 dedup + T-065 NumPy DP**. Ablation note: kernel DP table shows NumPy alone; closed-loop gains stack both (dedup reduces MF calls after resample).

### Uniqueness hit rate (after tip, short P1 probe)

N=16, 6 days, instrumented `mean_field_update` calls:

- particle-days = 96  
- MF calls = 82 → **0.85 calls / particle-day** (naive = 1.0)  
- ~15% call reduction on this short empty-ish start; larger after ESS collapse / duplicates in longer runs.

## 4. Production-hour re-estimate (honest)

Brainstorm charged ~**10⁸** LL/DP solves and **many-hundreds to low-thousands CPU-h** for a full production grid when P1+F2a dominate.

Using closed-loop factors (~**8–11×** on the hot columns) as the primary multiplier:

| Estimate | Before (order) | After ×~10 | Residual |
|----------|----------------|------------|----------|
| Hot P1+F2a CPU-h | hundreds–thousands | **tens–low hundreds** | Still multi-machine-day on a laptop for full β×rep grid |
| Blog “overnight on one box” | no | **still tight** | Stagewise design / budget cuts / Numba still on the table if needed |

**Do not claim headline VOI $.** Density remains exact sequential-WOR (ADR 0090 / 0103).

## 5. Math-unchanged attestation

- T-064: posteriors equal naive per-particle MF; call count == unique keys.  
- T-065: DP tables match frozen pure-Python reference at `rtol=0`, `atol=0` on small grids; structural NumPy rewrite.  
- Reviews: `.team/reviews/T-064.md`, `.team/reviews/T-065.md` **APPROVED**.  
- Verify: `.team/qa/T-064-verify.md`, `.team/qa/T-065-verify.md` **PASS** (pytest ≥495/501, coverage ≥89%).

## Leftover risks

1. Full production grid still expensive — speedups help but may not alone hit citeable overnight budget.  
2. Unique-hit rate is workload-dependent; short probes understate long-horizon resample duplicates.  
3. Tiny DP states can be slightly slower under NumPy (see [8,8]).  
4. Optional within-MF LL memo not implemented (allowed thin win; non-blocking).  
5. Human merge to `main` still required.
