# 0134. Protection-interval demand quantile via Monte Carlo

STATUS: ACCEPTED
DATE: 2026-08-17
BOARD-ID: CAL-B4
GROUP: CAL
TIER: 1
RELATED: 0113, 0116, T-132

## Context

ADR 0113 notes protection quantiles become sums of heterogeneous daily NBs once
calendar μ(day) lands. Closed-form `NB(n·r, p)` assumes i.i.d. daily demand and
misstates weekend-heavy MWF protection windows.

## Decision

1. **Default estimator:** Monte Carlo with `n_mc = 20_000` replicates, summing
   independent `NB(μ(start_day+k), demand_vm)` draws per protection day `k`.
2. **Quantile:** discrete empirical α-quantile with **higher** method (integer
   `d_star` suitable for case rounding).
3. **Determinism:** MC uses a **planning seed** derived from
   `(start_day, protection_days, alpha)` — independent of episode CRN
   (`PHYSICS_RUN_ID`, demand streams). Controllers remain deterministic given
   calendar inputs.
4. **Fast paths:** skip MC when no profile (legacy scipy path) or when all window
   μs are equal (single closed-form with window μ).
5. **Parity:** Rust kernel implements the same algorithm and seed derivation.

## Alternatives considered

- **Normal approximation** — rejected: understates tail risk at α≈0.9.
- **FFT convolution of PMFs** — rejected for v1: more code; MC sufficient at n≤4.
- **Episode-CRN coupling** — rejected: would make planning target stochastic.

## Consequences

**Easy:** calendar-consistent `d_star`; optimal α should move interior when profile
attached.

**Hard:** small MC noise (≤1 case at default N); golden tests pin seed + N.
