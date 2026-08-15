# FIL-11 Stage A — scenario contraction sweep

Oliver request: re-run Stage A metric under dwell / picking / spoilage knobs. **No production filter likelihood changes.**

## Honesty (production settle)

F2a/F2 age information comes from **priors** (arrival prior / birth prior at receipt).
P0/P1/F1 do **not** claim in-store age learning as a production gate; residual
contraction grids below are historical diagnostics, not a reopen of in-store age learning.

Settings (shared unless noted): K=8, N=500, L_filter=3, n_burn=20, n_score=30, seed=21, pass if full-mix posterior_sd < prior_sd × 0.95 and tight-spread control check.

**Metric note:** posterior is `age_posterior(0)` (oldest fixed slot), same as baseline Stage A. No single-cohort-from-birth API in the production particle filter; longer_score only lengthens the observation window.

| scenario | L p50 | L max | prior_sd | post_sd | Δ% | contracted? | pass/fail |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| baseline | 2.0 | 3 | 1.9805 | 2.2274 | -12.5% | no | **FAIL** |
| slower_mu15 | 3.0 | 4 | 1.9805 | 2.1935 | -10.8% | no | **FAIL** |
| longer_dwell_S120 | 5.0 | 7 | 1.9805 | 2.0120 | -1.6% | no | **FAIL** |
| slower_mu15_S120 | 7.0 | 8 | 1.9805 | 1.5705 | +20.7% | yes | **PASS** |
| fresh_bias_sigma0.25 | 2.0 | 3 | 1.9805 | 1.9656 | +0.8% | no | **FAIL** |
| fresh_bias_sigma0.2 | 1.0 | 3 | 1.9805 | 2.1171 | -6.9% | no | **FAIL** |
| uniform_picking | 2.0 | 3 | 1.9805 | 2.2096 | -11.6% | no | **FAIL** |
| weibull_beta3.5 | 2.0 | 4 | 1.9805 | 1.9269 | +2.7% | no | **FAIL** |
| weibull_beta4.0 | 2.0 | 4 | 1.9805 | 1.6649 | +15.9% | yes | **PASS** |
| cooler_store_T1C | 2.0 | 4 | 1.9805 | 2.1683 | -9.5% | no | **FAIL** |
| longer_score_n60 | 2.0 | 3 | 1.9805 | 2.1943 | -10.8% | no | **FAIL** |

## Notes per scenario

- **baseline**: defaults μ=30 V/M=2 S=60 σ=0.5 β=2 T=4°C; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/baseline.png`
- **slower_mu15**: demand μ=15, V/M=2, S=60; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/slower_mu15.png`
- **longer_dwell_S120**: S=120 base-stock (μ=30); tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/longer_dwell_S120.png`
- **slower_mu15_S120**: μ=15 and S=120 combined; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/slower_mu15_S120.png`
- **fresh_bias_sigma0.25**: stronger fresh-bias linger σ=0.25; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/fresh_bias_sigma0.25.png`
- **fresh_bias_sigma0.2**: stronger fresh-bias linger σ=0.2; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/fresh_bias_sigma0.2.png`
- **uniform_picking**: MOD-25 sensitivity uniform_picking=True; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/uniform_picking.png`
- **weibull_beta3.5**: more age-sensitive spoilage β=3.5; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/weibull_beta3.5.png`
- **weibull_beta4.0**: more age-sensitive spoilage β=4.0; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/weibull_beta4.0.png`
- **cooler_store_T1C**: slower in-store ageing T_store=1°C; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/cooler_store_T1C.png`
- **longer_score_n60**: longer score window n_score=60; metric still oldest slot; tight_post_sd=0.0000; fig=`/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios/longer_score_n60.png`

## Interpretation (for Oliver)

Baseline reproduces the documented Stage A failure (prior_sd≈1.98, posterior widens). Two knobs restore ≥5% contraction under the same metric: (1) **long dwell** — μ=15 combined with S=120 (+20.7% contraction; L p50/max = 7/8), while μ=15 or S=120 alone do not clear the threshold (S=120 only stops the blow-up); (2) **sharper spoilage** — Weibull β=4.0 (+15.9%), with β=3.5 only a weak +2.7% miss. Fresh-bias σ≤0.25, uniform picking, cooler T_store=1°C, and a longer score window do **not** restore contraction. Caveat: when empirical L exceeds L_filter=3 (slow-dwell cells), the particle filter still only tracks three slots and the reported posterior remains the oldest slot — so the μ15+S120 PASS is encouraging but not a single-cohort-from-birth proof.

Figure directory: `/home/oliver/blog/blueberries-voi/figures/m1/fil11_a_scenarios`
Grid: `figures/m1/fil11_a_scenarios/grid.png`
