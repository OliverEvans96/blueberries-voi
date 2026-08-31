---
title: Protection demand under a calendar
sources:
  code: [crates/voi_core/src/policy.rs, crates/voi_core/src/schedule.rs, src/blueberries_voi/model/demand_fractile.py, src/blueberries_voi/sim/order_schedule.py]
---

# Protection demand under a calendar

The ordering rule (see [The ordering rule](/control/ordering-rule)) needs a target: how much total demand should today's order be able to cover? That target is $F^{-1}_{D}(\alpha)$, the $\alpha$-quantile of demand summed over the **protection window** — the days between now and the next time the store can place another order and have it arrive. This page is about computing that quantile once the delivery calendar makes the window's length, and the demand within it, vary from one order day to the next.

## The idea

"Protection window" is the number of days a single order has to hold the shelf, on its own, before the next order can restock it. Under a delivery-every-day world this would always be one or two days. But this project's delivery calendar isn't daily — deliveries (and the orders that trigger them) land on specific weekdays — so the protection window's length depends on which weekday the order is placed. An order placed the day before a long gap between deliveries has to cover more days of demand than one placed right before a short gap.

Once the protection window's length is fixed, the next question is: how much demand should the order defend against? Not the *average* demand over that window — that would leave the store short about half the time. Instead, the target is a high **quantile** of total demand: the $\alpha$-quantile (default $\alpha = 0.9$), chosen so demand exceeding the order is a relatively rare event, not a coin flip. When the average daily demand is the same on every day in the window, this quantile of the *sum* has a clean closed-form answer. When the calendar makes some days busier than others within the same window, there's no clean formula for the sum of those mismatched days, so the quantile is estimated by simulation instead.

## The math

Demand on a single day is modelled as a negative binomial: mean $\mu$, variance-to-mean ratio $\text{demand\_vm} > 1$ (overdispersed relative to Poisson). The protection window covers $n$ days starting at day $t$; total protection demand is $D = \sum_{i=0}^{n-1} D_{t+i}$.

**Flat-mean case (closed form).** If every day in the window has the same mean $\mu$, the sum of i.i.d. negative binomials is itself negative binomial, and its quantile has a direct formula: with $r = \mu / (\text{demand\_vm} - 1)$ per day, the summed shape parameter is $r_{\text{sum}} = r \cdot n$ and success probability $p = r / (r + \mu)$, giving

$$
F^{-1}_{D}(\alpha) = \text{NB-PPF}(\alpha;\, r_{\text{sum}},\, p)
$$

read off directly from the negative binomial's inverse CDF.

**Calendar-varying case (Monte Carlo).** When the calendar profile makes the daily means $\mu_{t}, \mu_{t+1}, \dots, \mu_{t+n-1}$ differ from each other, the sum of non-identical negative binomials has no simple closed form for its quantile. The model falls back to simulation: draw many independent samples of each day's demand from its own negative binomial, sum them per draw, and read off the $\alpha$-quantile as an order statistic across draws — **20,000** draws by default. The random draws are deterministically seeded from the order day, protection-window length, and $\alpha$ itself, so the same planning inputs always reproduce the same quantile, run to run.

## Why it's modelled this way

The protection window's length comes directly from the delivery calendar: under the project's default **Monday/Wednesday/Friday** delivery calendar with a one-day lead time, orders can be placed on **Tuesday, Thursday, and Sunday** (the days that, one lead-time day later, line up with a delivery day). The number of protection days is not the same for every order day — it's the number of days until the *following* order's delivery arrives:

| Order day | Protection window | Covers through |
| --- | --- | --- |
| Tuesday | 3 days | the delivery from Thursday's order, arriving Friday |
| Thursday | 4 days | the delivery from Sunday's order, arriving Monday |
| Sunday | 3 days | the delivery from Tuesday's order, arriving Wednesday |

The choice of $\alpha$ itself — the quantile level, not the window length — is covered on [Why not the textbook fractile](/control/why-not-textbook-fractile); this page is only about computing $F^{-1}_D(\alpha)$ once $\alpha$ and the window are fixed.

The Monte Carlo fallback for the heterogeneous-mean case is a pragmatic choice rather than a derived one: rather than deriving (or approximating analytically) the quantile of a sum of non-identical negative binomials, the model draws enough independent per-day samples that the empirical quantile is stable, and fixes the seed so the same order day, window length, and $\alpha$ always reproduce the same answer — important for reproducible comparisons across policy arms and repeated runs.

**Honest caveat.** Monte Carlo means the calendar-varying quantile is an *estimate*, not an exact value — with a finite draw count there's inherent sampling noise, though the deterministic seeding means that noise is at least consistent and repeatable rather than different on every run. The flat-mean closed form, by contrast, is exact given the negative-binomial model assumption itself.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Protection demand quantile, top-level router (Rust) | $F^{-1}_D(\alpha)$ | `crates/voi_core/src/policy.rs:143` ([`protection_demand_quantile`](/api/rust/voi_core/policy/fn.protection_demand_quantile.html)) |
| Protection demand quantile, top-level router (Python) | $F^{-1}_D(\alpha)$ | `src/blueberries_voi/model/demand_fractile.py:91` (`protection_interval_quantile`) |
| Flat-mean closed form | $\text{NB-PPF}(\alpha; r_{\text{sum}}, p)$ | `crates/voi_core/src/policy.rs:42` (`homogeneous_closed_form`); `src/blueberries_voi/model/demand_fractile.py:46` (`_homogeneous_closed_form`) |
| Calendar-varying Monte Carlo fallback | — | `crates/voi_core/src/policy.rs:60` (`heterogeneous_nb_sum_quantile_mc`); `src/blueberries_voi/model/demand_fractile.py:58` (`heterogeneous_nb_sum_quantile_mc`) |
| Monte Carlo draw count, default | $n_{\text{mc}} = 20{,}000$ | `crates/voi_core/src/policy.rs:13` (`PROTECTION_MC_DEFAULT_N`); `src/blueberries_voi/model/demand_fractile.py:15` (`PROTECTION_MC_DEFAULT_N`) |
| Deterministic MC seed derivation | — | `crates/voi_core/src/policy.rs:21` ([`derive_protection_mc_seed`](/api/rust/voi_core/policy/fn.derive_protection_mc_seed.html)); `src/blueberries_voi/model/demand_fractile.py:19` (`derive_protection_mc_seed`) |
| Protection window length for a given order day | $n$ | `crates/voi_core/src/schedule.rs:109` ([`OrderSchedule::protection_days`](/api/rust/voi_core/schedule/struct.OrderSchedule.html#method.protection_days)); `src/blueberries_voi/sim/order_schedule.py:86` (`OrderSchedule.protection_days`) |
| Default delivery / order weekdays | Mon/Wed/Fri delivery; Tue/Thu/Sun order | `crates/voi_core/src/schedule.rs:15` (`OrderSchedule::default`, via `with_delivery(&[0, 2, 4], 1)`); `src/blueberries_voi/sim/order_schedule.py:22-24` (`_DEFAULT_DELIVERY`, `_DEFAULT_LEAD_TIME`, `_DEFAULT_ORDER`) |

## Caveats

- The 20,000-draw Monte Carlo estimate carries sampling noise like any Monte Carlo quantile; it is deterministic run-to-run (fixed seed derivation) but not exact the way the flat-mean closed form is.
- The negative-binomial demand model itself — including the overdispersion parameter `demand_vm` — is an assumption about the *shape* of day-to-day demand variation, not something this page independently validates; days with very different demand dynamics from what the negative binomial captures would not be represented faithfully in $F^{-1}_D(\alpha)$.
- This page describes the protection-window mechanics under the project's calendar-based demand and delivery model. It does not cover how the calendar's mean demand profile itself ($\mu(\text{day})$) is constructed — see [Demand: a calendar, not a coin](/store/demand-calendar) for that.
