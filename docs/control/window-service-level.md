---
title: Window service-level ordering
sources:
  code: [crates/voi_core/src/protection_sim.rs, crates/voi_core/src/session.rs]
---

# Window service-level ordering

This page describes an alternate ordering rule that was tried in place of the [damped survival-weighted ordering rule](/control/ordering-rule) used elsewhere on this site. It's kept here as reference detail for readers who want to see a different design that was tested and set aside, not as a feature in active use.

## The idea

The main ordering rule targets a single-day quantile of demand: it asks "how much demand should I be ready for on a typical bad day within the protection window?" and orders enough to cover that. The window service-level controller asks a different, stricter question instead: across the *entire* protection window — the full stretch of days a single order has to hold the shelf until the next order can arrive — what's the smallest order quantity whose probability of *zero* stockout days is at least some target probability? Rather than sizing against one day's worth of demand risk, it directly targets a probability of never running out across the whole window, then applies the same damping idea as the main rule to trade some of that safety margin back for less waste.

Two implementations of this idea were built:

- A **Monte Carlo reference version** (`sla_mc`) that simulates many random day-by-day scenarios of demand and spoilage over the protection window, using the same random draws across comparisons so only what's being tested differs (this is the common random numbers technique — see [The ordering rule](/control/ordering-rule) for more on the project's general modeling approach). It counts how often the shelf never runs dry, and searches for the smallest order quantity that clears the target probability. This is slow but treats the joint, day-by-day nature of the problem exactly, so it serves as an accuracy check for the faster method below.
- A **faster, approximate version** (`sla_pb`) that skips the simulation and instead computes the same probability analytically, treating each unit's chance of still being available on a given day as its own coin flip and combining all of those chances into one probability distribution over "how many units survive" — a Poisson-binomial calculation (a Poisson-binomial distribution is what you get from summing many yes/no events that each have their own, slightly different probability of a "yes"). This trades a small amount of accuracy for a large speedup.

Like the main ordering rule, the window service-level rule then damps its raw order quantity by a factor $\rho$ before rounding to a case multiple — but here the damping factor plays a different role than in the main rule. In the main rule, $\rho$ corrects a known over-reaction of plain base-stock ordering. Here, $\rho$ is simply a dial for trading service level against waste: turning it down orders less (accepting more stockout risk to cut waste), turning it up orders more (accepting more waste to cut stockout risk).

**Result.** This controller was one of two alternate designs tried against the main ordering rule (the other being a finite-horizon rollout controller). Neither improved profit meaningfully in testing — both remained short-sighted in a similar way to the main rule, which only optimizes over the days until the next order rather than the berries' full shelf life. See [The ordering rule](/control/ordering-rule) for the fuller discussion of why sharper information doesn't automatically translate into more profit in this project's experiments.

## In the code

| Piece | Location |
|-------|----------|
| Protection-window simulator | `crates/voi_core/src/protection_sim.rs` |
| Monte Carlo order rule | `sla_mc_order_f_belief` (`crates/voi_core/src/protection_sim.rs:507`) |
| Poisson-binomial order rule | `sla_pb_order_f_belief` (`crates/voi_core/src/protection_sim.rs:573`) |
| Session `act` arms (`"sla_mc"`, `"sla_pb"`) | `crates/voi_core/src/session.rs` |

See also [The ordering rule](/control/ordering-rule) and [Protection demand under a calendar](/control/protection-demand).
