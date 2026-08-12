# FIL-13 scaling & effectiveness (Oliver deep-dive)

Companion to [`fil13_bakeoff.md`](fil13_bakeoff.md) / ADR 0082. Broader microbench, slow-turn L, grocery interpretation, and when each backend is appropriate.

## Part A - Grocery interpretation of M1 defaults

Think of one store selling one blueberry SKU (punnets):

- **Demand:** about **30 punnets/day** (~**3.8 cases/day** at case size 8). Demand is a bit jumpy (V/M=2.0).
- **Ordering:** age-blind base-stock **S=60** punnets (~**7.5 cases** on the shelf target) with **daily delivery, 1-day lead time**. That is roughly two days of mean demand cover.
- **Picking:** sigma=0.5 is a **mild fresh bias** - shoppers prefer fresher trays a bit, but not pure LIFO. Strong LIFO would be sigma<<1.
- **Spoilage:** Weibull beta=2.0, eta=14 days at 0 degC; store fridge **4 degC** with Q10=3 => effective age runs ~**1.55x** calendar, so characteristic life is ~**9.0 calendar days** on the shelf - still long vs a ~2-day turn.

### Shelf dwell and why measured L is tiny

With ~30 sold/day from ~60 on hand, inventory **turns in about two days**. Daily deliveries add a new lot when the store reorders, but older lots empty quickly through sales (and mild fresh-bias still lets older stock move). Extinct lots (count->0) drop out. So live lot count L stays small:

- baseline scored window: **p50=2.00, p90=3.00, max=4, mean=2.02**

That matches intuition: a fast-turning berry facing with daily truck arrivals rarely has more than a couple of overlapping delivery lots.

### Is the "6 lots ceiling" about the store?

**No - it is about filter memory, not store reality.** `full_joint` budgets `K^L*N` floats. At production K=8, N=2000 the guard trips near L~6 (`8^6*2000 ~ 5.2e7` vs budget `5e+07`). The bakeoff "OOM at L>=6" is that **guard**, not a claim that the store keeps six lots. Under M1 defaults the store typically has **2-4** live lots.

### What would push L toward 6-15?

- **Slower sales** (lower mu) -> lots linger.
- **Larger target stock / bigger orders** (higher S, larger cases) -> more overlapping deliveries before the first sells out.
- **Stronger LIFO** (smaller sigma) -> old lots stay while new ones sell.
- **Colder store** (slower spoilage) -> old lots die slower, so they remain as live cohorts longer.
- **Less frequent delivery** (e.g. every 2 days with larger protection stock) -> each arrival is bigger and more cohorts can coexist if picking is LIFO-ish.

## Part B - Scaling microbench

### Memory proxies (design formulas x 8 bytes)

| backend | floats proxy |
| --- | --- |
| `full_joint` | `K^L * N` (guarded; budget `5e+07`) |
| `sliding_window` W | `(K^W + max(0,L-W)*K) * N` |
| `mean_field` | `L * K * N` |
| `bound_L` (max_L=4) | `K^{min(L,4)} * N` |
| `bootstrap_pf` | `N * L` (age indices; no grid posterior) |

**Implementation note:** the current bakeoff stubs store `age_post` as shape `(N, L, K)` for RBPF-style backends and share the same per-cohort update. `full_joint`'s distinctive behavior in this repo is the **`K^L*N` memory guard** (true dense joint tensor is not materialized). Sliding-window `window` is accepted but not yet used to change the update. Treat runtime differences among `full_joint` / `sliding_window` / `mean_field` as small; treat **memory formulas** as the decision surface for FIL-13.

Soft skip if floats proxy > `2e+08`; per-cell timeout ~ `8` s; `3` predict/update steps.

### Sample rows (K=8, N=200)

| backend | K | N | L | wall_s | peak_MB | floats_proxy | flag | tv |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full_joint | 8 | 200 | 2 | 0.0110 | 0.1 | 1.28e+04 | ok | 0.0000 |
| full_joint | 8 | 200 | 3 | 0.0145 | 0.2 | 1.02e+05 | ok | 0.0000 |
| full_joint | 8 | 200 | 4 | 0.0162 | 0.2 | 8.19e+05 | ok |  |
| full_joint | 8 | 200 | 6 | 0.0000 | 0.0 | 5.24e+07 | skip |  |
| full_joint | 8 | 200 | 8 | 0.0000 | 0.0 | 3.36e+09 | skip |  |
| full_joint | 8 | 200 | 10 | 0.0000 | 0.0 | 2.15e+11 | skip |  |
| full_joint | 8 | 200 | 12 | 0.0000 | 0.0 | 1.37e+13 | skip |  |
| full_joint | 8 | 200 | 15 | 0.0000 | 0.0 | 7.04e+15 | skip |  |
| sliding_window | 8 | 200 | 2 | 0.0112 | 0.1 | 1.02e+05 | ok | 0.0000 |
| sliding_window | 8 | 200 | 3 | 0.0118 | 0.2 | 1.02e+05 | ok | 0.0000 |
| sliding_window | 8 | 200 | 4 | 0.0154 | 0.2 | 1.04e+05 | ok |  |
| sliding_window | 8 | 200 | 6 | 0.0183 | 0.3 | 1.07e+05 | ok |  |
| sliding_window | 8 | 200 | 8 | 0.0261 | 0.4 | 1.10e+05 | ok |  |
| sliding_window | 8 | 200 | 10 | 0.0307 | 0.4 | 1.14e+05 | ok |  |
| sliding_window | 8 | 200 | 12 | 0.0397 | 0.5 | 1.17e+05 | ok |  |
| sliding_window | 8 | 200 | 15 | 0.0367 | 0.6 | 1.22e+05 | ok |  |
| mean_field | 8 | 200 | 2 | 0.0070 | 0.1 | 3.20e+03 | ok | 0.0000 |
| mean_field | 8 | 200 | 3 | 0.0096 | 0.2 | 4.80e+03 | ok | 0.0000 |
| mean_field | 8 | 200 | 4 | 0.0129 | 0.2 | 6.40e+03 | ok |  |
| mean_field | 8 | 200 | 6 | 0.0164 | 0.3 | 9.60e+03 | ok |  |
| mean_field | 8 | 200 | 8 | 0.0190 | 0.4 | 1.28e+04 | ok |  |
| mean_field | 8 | 200 | 10 | 0.0276 | 0.4 | 1.60e+04 | ok |  |
| mean_field | 8 | 200 | 12 | 0.0274 | 0.5 | 1.92e+04 | ok |  |
| mean_field | 8 | 200 | 15 | 0.0338 | 0.6 | 2.40e+04 | ok |  |
| bootstrap_pf | 8 | 200 | 2 | 0.0022 | 0.1 | 4.00e+02 | ok |  |
| bootstrap_pf | 8 | 200 | 3 | 0.0020 | 0.1 | 6.00e+02 | ok |  |
| bootstrap_pf | 8 | 200 | 4 | 0.0019 | 0.1 | 8.00e+02 | ok |  |
| bootstrap_pf | 8 | 200 | 6 | 0.0028 | 0.2 | 1.20e+03 | ok |  |
| bootstrap_pf | 8 | 200 | 8 | 0.0046 | 0.2 | 1.60e+03 | ok |  |
| bootstrap_pf | 8 | 200 | 10 | 0.0032 | 0.3 | 2.00e+03 | ok |  |
| bootstrap_pf | 8 | 200 | 12 | 0.0025 | 0.3 | 2.40e+03 | ok |  |
| bootstrap_pf | 8 | 200 | 15 | 0.0018 | 0.4 | 3.00e+03 | ok |  |
| bound_L | 8 | 200 | 2 | 0.0082 | 0.1 | 1.28e+04 | ok |  |
| bound_L | 8 | 200 | 3 | 0.0121 | 0.2 | 1.02e+05 | ok |  |
| bound_L | 8 | 200 | 4 | 0.0134 | 0.2 | 8.19e+05 | ok |  |
| bound_L | 8 | 200 | 6 | 0.0106 | 0.2 | 8.19e+05 | ok |  |
| bound_L | 8 | 200 | 8 | 0.0136 | 0.2 | 8.19e+05 | ok |  |
| bound_L | 8 | 200 | 10 | 0.0140 | 0.2 | 8.19e+05 | ok |  |
| bound_L | 8 | 200 | 12 | 0.0127 | 0.2 | 8.19e+05 | ok |  |
| bound_L | 8 | 200 | 15 | 0.0106 | 0.2 | 8.19e+05 | ok |  |

### Extra cells (K∈{4,6,8,10}, N∈{200,500,2000}) - condensed

Full matrix is large; highlights:

**`full_joint` feasibility frontier** (first skip/oom per K,N):

| K | N | max L ok | first fail L | reason |
| --- | --- | --- | --- | --- |
| 4 | 200 | 8 | 10 | joint guard K^L*N=2.10e+08 > 5.00e+07 |
| 4 | 500 | 8 | 10 | joint guard K^L*N=5.24e+08 > 5.00e+07 |
| 4 | 2000 | 6 | 8 | joint guard K^L*N=1.31e+08 > 5.00e+07 |
| 6 | 200 | 6 | 8 | joint guard K^L*N=3.36e+08 > 5.00e+07 |
| 6 | 500 | 6 | 8 | joint guard K^L*N=8.40e+08 > 5.00e+07 |
| 6 | 2000 | 4 | 6 | joint guard K^L*N=9.33e+07 > 5.00e+07 |
| 8 | 200 | 4 | 6 | joint guard K^L*N=5.24e+07 > 5.00e+07 |
| 8 | 500 | 4 | 6 | joint guard K^L*N=1.31e+08 > 5.00e+07 |
| 8 | 2000 | 4 | 6 | joint guard K^L*N=5.24e+08 > 5.00e+07 |
| 10 | 200 | 4 | 6 | joint guard K^L*N=2.00e+08 > 5.00e+07 |
| 10 | 500 | 4 | 6 | joint guard K^L*N=5.00e+08 > 5.00e+07 |
| 10 | 2000 | 4 | 6 | joint guard K^L*N=2.00e+09 > 5.00e+07 |

### Sliding window W=2 vs W=3 (memory formula + smoke time)

| backend | K | N | L | wall_s | floats_proxy | note |
| --- | --- | --- | --- | --- | --- | --- |
| sliding_window_W2 | 8 | 200 | 3 | 0.0118 | 1.44e+04 | timed |
| sliding_window_W2 | 8 | 200 | 6 | 0.0000 | 1.92e+04 | memory formula only (window unused in stub) |
| sliding_window_W2 | 8 | 200 | 12 | 0.0000 | 2.88e+04 | memory formula only (window unused in stub) |
| sliding_window_W3 | 8 | 200 | 3 | 0.0089 | 1.02e+05 | timed |
| sliding_window_W3 | 8 | 200 | 6 | 0.0000 | 1.07e+05 | memory formula only (window unused in stub) |
| sliding_window_W3 | 8 | 200 | 12 | 0.0000 | 1.17e+05 | memory formula only (window unused in stub) |

## Slow-turn regimes (empirical L, 20 burn + 90 score)

| regime | p50 | p90 | max | mean |
| --- | --- | --- | --- | --- |
| baseline mu=30 S=60 sigma=0.5 daily | 2.00 | 3.00 | 4 | 1.87 |
| slow sales mu=15 | 4.00 | 5.00 | 7 | 3.78 |
| fat stock S=120 | 4.00 | 6.00 | 7 | 4.07 |
| strong LIFO sigma=0.2 | 2.00 | 3.00 | 4 | 1.71 |
| delivery every 2d (S=90) | 1.00 | 1.00 | 2 | 1.04 |
| combo mu=15 sigma=0.2 S=120 | 8.00 | 9.10 | 13 | 7.78 |

Highest max L among regimes: **combo mu=15 sigma=0.2 S=120** -> max=13. Optional bakeoff cells at forced L=13, K=8, N=200:

| backend | wall_s | floats_proxy | flag |
| --- | --- | --- | --- |
| full_joint | 0.0000 | 1.10e+14 | skip |
| sliding_window | 0.0343 | 1.18e+05 | ok |
| mean_field | 0.0301 | 2.08e+04 | ok |
| bootstrap_pf | 0.0020 | 2.60e+03 | ok |

## Effectiveness / appropriateness

### Accuracy: TV vs exact one-step update (K=4)

| backend | L | K | TV |
| --- | --- | --- | --- |
| full_joint | 2 | 4 | 0.000000 |
| sliding_window | 2 | 4 | 0.000000 |
| mean_field | 2 | 4 | 0.000000 |
| full_joint | 3 | 4 | 0.000000 |
| sliding_window | 3 | 4 | 0.000000 |
| mean_field | 3 | 4 | 0.000000 |
| full_joint | 4 | 4 | 0.000000 |
| sliding_window | 4 | 4 | 0.000000 |
| mean_field | 4 | 4 | 0.000000 |

### Approximation error: posterior TV between backends (K=4)

| A | B | L | TV(A,B) |
| --- | --- | --- | --- |
| sliding_window | full_joint | 2 | 0.000000 |
| mean_field | full_joint | 2 | 0.000000 |
| sliding_window | full_joint | 3 | 0.000000 |
| mean_field | full_joint | 3 | 0.000000 |
| sliding_window | full_joint | 4 | 0.000000 |
| mean_field | full_joint | 4 | 0.000000 |

Near-zero TV among `full_joint` / `sliding_window` / `mean_field` is expected with the current shared factorized update stub.

### Bootstrap PF

Theory: putting age in the particle (no Rao-Blackwell grid) needs **much larger N** to match marginal age accuracy of an RBPF - variance scales like sampling a discrete age per cohort without marginalising. Quick ESS smoke (same toy obs):

- N=200: ESS after 10 steps ~ 188.1 (94.0% of N)
- N=2000: ESS after 10 steps ~ 1831.2 (91.6% of N)
- N=10000: ESS after 10 steps ~ 9269.0 (92.7% of N)

### Decision table - when is each OK?

| Backend | Use when | Avoid when |
| --- | --- | --- |
| **full_joint (E)** | Empirical L small (<=3-4 at K=8, N~2e3); want exact joint budget semantics + production lock | `K^L*N` near/over `5e7` (guard); policy regimes that raise L |
| **sliding_window (A)** | L grows; coupling strongest among youngest W lots; need fallback without full `K^L` | Need proven joint accuracy on long LIFO tails (implement W semantics first) |
| **mean_field (B)** | Diagnostics / speed; dependence weak | Allocation coupling matters and you need joint fidelity |
| **bound_L (C)** | Stress tests with capped state | Production sim (silently wrong if true L > cap) |
| **bootstrap_pf (D)** | Ablation / bakeoff arm | Production age posterior at modest N |

## Recommendation (Oliver)

1. **Store reality under M1 defaults:** L~2-3. The "ceiling of 6" is **filter memory**, not how many lots the grocery shelf carries.
2. **Keep `full_joint` for production** while measured L stays <=3-4 at K=8 / N=2000.
3. **Switch to sliding_window (or reopen FIL-13)** if a controller / cadence / LIFO regime pushes empirical L so the joint guard trips.
4. Slow-turn knobs (mu↓, S↑, sigma↓, less frequent delivery) can raise L; re-check empirical L before trusting the memory budget.

*Generated in 18.0s. Figure: `figures/m1/fil13_scaling.png`.*
