---
title: The VOI metric
sources:
  code: [src/blueberries_voi/voi/metric.py, src/blueberries_voi/voi/bootstrap.py, crates/voi_core/src/voi.rs]
---

# The VOI metric

Once the common random numbers (CRN) cell hands back one profit number per observation scenario (see [Same weather, different glasses](/economics/crn-seeding)), we still need to turn that ladder of numbers into one headline figure: how much is better information actually worth? CRN means every scenario in the comparison is run against the same underlying random draws, so the only thing that differs between them is what each one observed — that's what makes a clean, direct comparison possible. This page describes how the project turns those paired profit numbers into its Value of Information (VOI) metric: a percentage plus a supporting dollar amount, both measured against the least-informed scenario. That conversion happens in a small piece of Python, separate from the physics engine that produced the profits in the first place.

## The idea

Two scenarios' profits over the same simulated stretch of time — thanks to CRN pairing — can be subtracted directly: profit of the richer scenario, minus profit of the books-only scenario. That difference is a dollar figure. But a dollar figure alone doesn't say whether $12 is a big deal: for a corner store that made $200 that week it's a lot, for a chain store that made $50,000 it's noise. So the difference also gets turned into a percentage of the books-only baseline: does better information buy a 6% better week, or a 0.1% better week? The percentage is the headline number, because it's scale-free — a reader can translate it to their own store's size — while the dollar figure sticks around as supporting detail.

In practice, once this metric was computed across the whole observation ladder, the answer came out close to flat: every richer scenario landed within about 1% of the books-only baseline. Later pages get into why that happened — this page is only about how the number itself is calculated.

## The math

Let $\text{profit}_\text{scenario}$ be one observation scenario's scored profit for an episode (see [Profit accounting](/economics/profit-accounting)), and $\text{profit}_\text{base}$ be the books-only scenario's profit over that same shared physical realization — the same simulated days, demand draws, and spoilage outcomes, just observed differently. The metric reports both an absolute and a relative delta:

$$
\text{absolute\_delta} = \text{profit}_\text{scenario} - \text{profit}_\text{base}
\qquad\qquad
\text{pct\_vs\_p0} = \frac{\text{profit}_\text{scenario} - \text{profit}_\text{base}}{\text{profit}_\text{base}}
$$

Both numbers are always anchored to the books-only scenario — the least-informed scenario on the ladder — never to an adjacent scenario, so every scenario's Value of Information is directly comparable to every other scenario's.

A point estimate alone doesn't say how much to trust it, so every reported VOI number also carries a **paired bootstrap** confidence interval. Because common random numbers pair every scenario against the same underlying draws, what varies across replications is the difference between two paired outcomes, not two separately noisy averages. The bootstrap exploits this: it resamples replication indices, with replacement, from the array of already-paired differences, recomputes the mean of each resample, and reports the spread of those resampled means as the confidence interval. Pairing is what makes this interval tight enough to be useful — an unpaired interval built from the two raw averages would throw away the shared-randomness correlation the CRN scheme was built to create.

## Why it's modelled this way

The metric reports **both** the percentage and the dollar figure, rather than only a raw dollar delta between adjacent scenarios (concrete, but needs a store-size caveat to generalize) or only a percentage (scale-free, but hides the absolute stakes). Reporting both costs nothing extra, since both numbers come from the same subtraction, and it lets a reader translate the headline to their own store's scale.

A percentage computed against a small, zero, or noisy denominator is unreliable — a store having an unusually bad books-only week by chance would inflate every percentage built on top of it. The code guards against the worst case directly: it raises an error rather than silently returning a garbage or infinite percentage when the books-only scenario's profit is exactly zero. A small but noisy nonzero denominator can still produce a swingy percentage without tripping that guard; if that turns out to matter in practice, a more stable reference point — such as a simple always-order-the-same-amount baseline — could be used instead of the books-only scenario.

The paired bootstrap confidence interval follows the same pairing rule used everywhere else on this site that profit comparisons are reported: whenever a comparison is paired by CRN, its interval should be computed on the paired differences, not on the two raw averages separately. A point estimate alone would understate how much confidence to place in any one number. Showing the full bootstrap distribution as a chart for every comparison would be richer, but it's more figure-design work than a headline number needs by default — that's reserved for a specific comparison whose interval turns out surprisingly wide.

**A note on where this lives.** The physics engine itself has no notion of "VOI" as a computed metric — it only returns a list of per-scenario profits. Every piece of delta, percentage, and bootstrap arithmetic described on this page lives one layer above, in the project's Python code, not in the Rust simulator. This codebase also doesn't use the classical decision-theory terms EVSI or EVPI (Expected Value of Sample or Perfect Information) — the ladder of paired profit deltas described here is this project's own, simpler notion of value of information, not an implementation of that textbook framework.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Percentage headline vs. books-only scenario | `pct_vs_p0` | `src/blueberries_voi/voi/metric.py:32` |
| Supporting absolute dollar delta | `absolute_delta` | `src/blueberries_voi/voi/metric.py:31` |
| Metric container | `VoIMetric` | `src/blueberries_voi/voi/metric.py:14` |
| Metric function | `voi_vs_p0` | `src/blueberries_voi/voi/metric.py:21` |
| Zero-denominator guard (raises rather than returning garbage) | — | `src/blueberries_voi/voi/metric.py:28-30` |
| Paired bootstrap confidence interval | `paired_bootstrap_ci` | `src/blueberries_voi/voi/bootstrap.py:30` |
| Bootstrap resample of paired replication indices | `idx = rng.integers(...)` | `src/blueberries_voi/voi/bootstrap.py:55` |
| Bootstrap result container (mean + percentile interval) | `BootstrapCI` | `src/blueberries_voi/voi/bootstrap.py:20` |
| Per-scenario profits only — no VOI arithmetic here | `run_voi_crn_cell` | `crates/voi_core/src/voi.rs:416` |

## Caveats

- The percentage is unreliable near a small or noisy books-only-scenario denominator — the code refuses to compute it at exactly zero, but a small nonzero (and noisy) denominator can still produce a swingy percentage even without tripping that guard.
- The bootstrap confidence interval only accounts for Monte Carlo sampling noise across replications. It does not account for uncertainty in the profit-cost parameters (deliberately chosen synthetic values — see [Profit accounting](/economics/profit-accounting) — not yet validated against a real store), or in the underlying physical model's own parameters.
- "VOI" here is always a *relative* comparison against the books-only scenario specifically, never an adjacent-scenario comparison and never an absolute measure of information's worth in isolation — a different anchor scenario would produce a different headline number for the exact same underlying profits.
- There is no EVSI/EVPI machinery in this codebase to cross-check against; the ladder-of-deltas approach described here has only been checked against its own internal CRN and bootstrap consistency checks, not against that classical framework.
