# FIL-13 tractability bakeoff

Empirical live-cohort counts under interim M1 defaults (σ=0.5, S=60, MOD-26 demand/case, FIL-14 extinction):
- p50=2.00, p90=3.00, max=3, mean=1.73

## Recommendation

Empirical L is **small** (p50≈2, p90≈3, max≈3), so `full_joint` (E) stays under the `K^L·N` memory budget at production (K=8, N=2000). Per the settle rule (prefer A if L large; E if L small enough), production locks **E — full_joint** (ADR 0082 ACCEPTED; `PRODUCTION_BACKEND=full_joint`). FIL-15 locks K=8 on [0,8], N=2000, ESS=N/2 (ADR 0083). **A — sliding_window** remains implemented as the bakeoff/fallback backend if a future policy regime pushes L up and trips the memory guard (`full_joint` OOMs at L≥6 in this bakeoff at K=8, N=200).

## Sample rows (K=8, N=200)

| backend | L | wall_s | oom | tv(L≤3) |
| --- | --- | --- | --- | --- |
| sliding_window | 2 | 0.0121 | False | 0.000 |
| sliding_window | 3 | 0.0107 | False | 0.000 |
| sliding_window | 4 | 0.0148 | False |  |
| sliding_window | 6 | 0.0241 | False |  |
| sliding_window | 8 | 0.0236 | False |  |
| sliding_window | 12 | 0.0307 | False |  |
| mean_field | 2 | 0.0118 | False | 0.000 |
| mean_field | 3 | 0.0138 | False | 0.000 |
| mean_field | 4 | 0.0168 | False |  |
| mean_field | 6 | 0.0200 | False |  |
| mean_field | 8 | 0.0260 | False |  |
| mean_field | 12 | 0.0349 | False |  |
| bound_L | 2 | 0.0125 | False |  |
| bound_L | 3 | 0.0139 | False |  |
| bound_L | 4 | 0.0141 | False |  |
| bound_L | 6 | 0.0163 | False |  |
| bound_L | 8 | 0.0137 | False |  |
| bound_L | 12 | 0.0146 | False |  |
| bootstrap_pf | 2 | 0.0024 | False |  |
| bootstrap_pf | 3 | 0.0021 | False |  |
| bootstrap_pf | 4 | 0.0041 | False |  |
| bootstrap_pf | 6 | 0.0036 | False |  |
| bootstrap_pf | 8 | 0.0024 | False |  |
| bootstrap_pf | 12 | 0.0023 | False |  |
| full_joint | 2 | 0.0122 | False | 0.000 |
| full_joint | 3 | 0.0145 | False | 0.000 |
| full_joint | 4 | 0.0163 | False |  |
| full_joint | 6 | 0.0000 | True |  |
| full_joint | 8 | 0.0000 | True |  |
| full_joint | 12 | 0.0000 | True |  |

## See also

Broader K/N/L microbench, slow-turn L regimes, grocery interpretation, and backend effectiveness notes: [`fil13_scaling.md`](fil13_scaling.md) (`figures/m1/fil13_scaling.png`).
