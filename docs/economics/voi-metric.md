---
title: The VOI metric
sources:
  code: [src/blueberries_voi/voi/metric.py, src/blueberries_voi/voi/bootstrap.py, crates/voi_core/src/voi.rs]
---

# The VOI metric

Once the CRN cell hands back one profit number per knowledge rung (see [Same weather, different glasses](/economics/crn-seeding)), the project still needs to turn that ladder of numbers into a single headline figure for "how much is better information worth." That conversion — a percentage plus a supporting dollar amount, both measured against the least-informed rung — happens in a small piece of Python, separate from the physics engine that produced the profits in the first place.

![Absolute dollar VOI vs P0 across β for the P1 and B-state rungs, with paired-bootstrap confidence bands (smoke-scale toy sweep)](/figures/voi-dollar-ribbon.png)

## The idea

Two rungs' profits over the *same* simulated week — thanks to CRN pairing — can be subtracted directly: profit(richer rung) minus profit(books-only rung). That difference is a dollar figure. But a dollar figure alone doesn't say whether \$12 is a big deal: for a corner store that made \$200 that week it's a lot, for a chain store that made \$50,000 it's noise. So the difference also gets expressed as a percentage of the books-only baseline: does better information buy a 6% better week, or a 0.1% better week? The percentage is the headline number, because it's scale-free — a reader can translate it to their own store's size — while the dollar figure sticks around as supporting detail.

## The math

Let $\text{profit}_\text{scenario}$ be one knowledge rung's scored episode profit (see [Profit accounting](/economics/profit-accounting)), and $\text{profit}_{P0}$ be the books-only rung's profit over the same shared physical realization. The metric reports both an absolute and a relative delta:

$$
\text{absolute\_delta} = \text{profit}_\text{scenario} - \text{profit}_{P0}
\qquad\qquad
\text{pct\_vs\_p0} = \frac{\text{profit}_\text{scenario} - \text{profit}_{P0}}{\text{profit}_{P0}}
$$

Both numbers are always anchored to $P0$, the least-informed rung on the knowledge ladder — never to an adjacent rung — so every scenario's VOI is directly comparable to every other scenario's.

A point estimate alone doesn't say how much to trust it, so every reported VOI number also carries a **paired bootstrap** confidence interval. Because CRN pairs every rung against the same underlying draws, the quantity that varies across replications is the *per-replication difference* itself, not two independently noisy means — so the bootstrap resamples replication indices (with replacement) from the array of already-paired deltas, recomputes the mean of each resample, and reports the resample distribution's percentiles as the interval. Pairing is what makes this interval tight enough to be useful: an unpaired, two-sample interval on the two raw means would throw away the shared-randomness correlation the CRN scheme was built to create.

## Why it's modelled this way

The metric reports **both** the percentage and the dollar figure, rather than only a raw dollar delta between adjacent rungs (concrete, but needs a store-size caveat to generalize) or only a percentage (scale-free, but obscures the absolute stakes). Reporting both costs nothing extra once both numbers exist from the same subtraction, and lets a reader translate the headline to their own store's scale.

A percentage computed against a small, zero, or noisy denominator is unreliable — a store having an unusually bad $P0$ week by chance would inflate every percentage built on top of it. `voi_vs_p0` guards against this: it raises `ValueError` rather than silently returning a garbage (or infinite) percentage when `profit_p0` is exactly zero. If this instability shows up in practice on a noisy-but-nonzero denominator, the fallback is to re-anchor the percentage against a more stable reference — such as the constant-order policy's floor profit — instead of $P0$ specifically.

The paired bootstrap CI follows the same pairing rule used everywhere else profit comparisons are reported: an interval on a policy comparison should be paired, extended here to cover every number the project reports, not just a rollout's inner candidate loop. A point estimate alone would understate how much confidence to place in any one number. Showing the full bootstrap distribution as a violin or histogram per comparison is richer but more figure-design work than a headline number needs by default — that's reserved as a diagnostic for a specific comparison whose interval turns out surprisingly wide.

**Architectural note.** `crates/voi_core/src/voi.rs`'s `run_voi_crn_cell` returns *only* a list of per-scenario profits — it has no notion of "VOI" as a computed metric at all. Every piece of delta/percentage/bootstrap arithmetic described on this page lives in Python (`voi/metric.py`, `voi/bootstrap.py`), one layer above the Rust physics. This codebase does not use the terms EVSI or EVPI (Expected Value of Sample/Perfect Information) from the classical decision-theory literature — the P0-to-oracle ladder of paired profit deltas described here is this project's own operational notion of value of information, not an implementation of that textbook framework.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Percentage headline vs. books-only rung | `pct_vs_p0` | `src/blueberries_voi/voi/metric.py:32` |
| Supporting absolute dollar delta | `absolute_delta` | `src/blueberries_voi/voi/metric.py:31` |
| Metric container | `VoIMetric` | `src/blueberries_voi/voi/metric.py:14` |
| Metric function | `voi_vs_p0` | `src/blueberries_voi/voi/metric.py:21` |
| Zero-denominator guard (raises rather than returning garbage) | — | `src/blueberries_voi/voi/metric.py:28-30` |
| Paired bootstrap CI | `paired_bootstrap_ci` | `src/blueberries_voi/voi/bootstrap.py:30` |
| Bootstrap resample of paired replication indices | `idx = rng.integers(...)` | `src/blueberries_voi/voi/bootstrap.py:55` |
| Bootstrap result container (mean + percentile interval) | `BootstrapCI` | `src/blueberries_voi/voi/bootstrap.py:20` |
| Per-scenario profits only — no VOI arithmetic here | `run_voi_crn_cell` | `crates/voi_core/src/voi.rs:352` |

## Caveats

- The percentage is unreliable near a small or noisy $P0$ denominator — the code refuses to compute it at exactly zero, but a small nonzero (and noisy) $P0$ can still produce a swingy percentage even without tripping that guard.
- The bootstrap CI only accounts for Monte Carlo sampling noise across replications; it does not account for uncertainty in the (currently uncalibrated) profit-cost parameters — see [Profit accounting](/economics/profit-accounting) — or in the underlying physical model's parameters themselves.
- "VOI" here is always a *relative* comparison against the $P0$ books-only rung specifically, never an adjacent-rung comparison and never an absolute measure of information's worth in isolation — a different anchor rung would produce a different headline number for the exact same underlying profits.
- There is no EVSI/EVPI machinery in this codebase to cross-check against; the ladder-of-deltas approach described here has only been checked against its own internal CRN/bootstrap consistency checks, not against that classical framework.
