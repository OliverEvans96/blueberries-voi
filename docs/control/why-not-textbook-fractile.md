---
title: Why not the textbook fractile
sources:
  code: [crates/voi_core/src/policy.rs, src/blueberries_voi/model/demand_fractile.py, src/blueberries_voi/controller/rung0.py, src/blueberries_voi/sim/alpha_tune.py]
---

# Why not the textbook fractile

The [previous page](/control/newsvendor) derived a clean formula for the best order quantity: order up to the $\frac{c_u}{c_u+c_o}$ quantile of demand. This project's ordering rule still orders up to *some* quantile of demand — but that quantile, called $\alpha$, is not computed from that formula. It's a **tuned service-level target** (0.9 by default) chosen by running simulated episodes and seeing which value produces the most profit. This page explains why.

## The idea

The textbook fractile $\frac{c_u}{c_u+c_o}$ answers a specific question: "if every leftover unit is destroyed at the end of the period, what's the best order quantity?" That's not the situation on the shelf here. A punnet of blueberries that doesn't sell today isn't thrown out — it's still there tomorrow, a bit less fresh, available to sell or spoil on some later day. Inventory carries over and keeps aging rather than resetting.

That breaks the assumption the textbook formula depends on. The real cost of an "extra" unit ordered today is some mix of a small holding cost and a chance the unit spoils later, and that chance depends on how the whole multi-day ordering policy behaves from here on — how aggressively future days re-order, how fruit already on the shelf gets picked versus left behind. There's no way to write that down as a clean, fixed number the way $c_o$ is fixed in the one-shot problem; it's entangled with the policy itself. Rather than deriving a corrected formula, this project sidesteps the derivation: it runs the full closed-loop system under a range of candidate $\alpha$ values and keeps whichever one comes out most profitable in simulation.

## The math

The ordering rule (see [the ordering rule page](/control/ordering-rule) for the full picture) has the shape

$$
q_t = \text{caseRound}\!\left(\big[F^{-1}_{D_{t:t+L}}(\alpha) - \tilde I_t\big]^+\right)
$$

where $D_{t:t+L}$ is demand over the protection interval (the days a new order must cover before the next order can arrive), $F^{-1}_{D_{t:t+L}}(\alpha)$ is the $\alpha$-quantile of that demand — structurally the same inverse-CDF quantity as $q^*$ on the newsvendor page — $\tilde I_t$ is effective inventory already on hand (see [Effective inventory](/control/effective-inventory)), $(\,\cdot\,)^+$ is $\max(\cdot, 0)$, and $\text{caseRound}$ rounds to the nearest case pack.

The difference from the textbook page is entirely in how $\alpha$ is chosen. There, $\alpha = \frac{c_u}{c_u+c_o}$, computed once from two fixed costs. Here, $\alpha$ is picked by grid search: for a set of candidate values $\{0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95\}$, the full closed-loop system — controller, filter, arrivals, demand — is simulated end to end for each candidate, and the $\alpha$ that yields the highest simulated episode profit is kept:

$$
\alpha^\star = \arg\max_{\alpha \,\in\, \text{grid}} \ \mathbb{E}\big[\text{episode profit} \mid \alpha\big]
$$

where the expectation is estimated by running scored simulation days under shared random numbers across candidates (so the comparison isn't just noise). This is a search over outcomes, not a derivation from costs — nothing here claims to solve for $\alpha^\star$ in closed form.

## Why it's modelled this way

A leftover unit here is usually sold tomorrow, so the true overage cost is closer to $h + c_w \cdot P(\text{outdates before selling})$ — a holding cost $h$ plus a waste cost $c_w$ weighted by the policy-dependent probability that the unit eventually spoils before it sells. That probability isn't something the closed-form newsvendor derivation can produce, because it depends on the ordering policy's own future behavior. Reporting the theoretical fractile as-is would be the wrong answer to this problem, since it assumes leftovers are destroyed, which isn't true here; showing it side by side with a tuned value as a reference comparison was considered but not adopted.

Tuning $\alpha$ by simulation recovers, empirically, a correction that the perishable-inventory literature derives analytically: service levels for perishable goods should sit above the naive newsvendor fractile (Nahmias 1976; Nandakumar & Morton 1993). Doing it by simulation avoids re-deriving that correction from scratch for this project's specific dynamics. Every policy arm compared in this project's evaluations uses its own tuned $\alpha$, because an untuned baseline is an easy way to manufacture a misleadingly bad comparison — leaving one arm's $\alpha$ un-tuned would quietly cripple it next to the others.

**Honest caveat.** The tuned $\alpha$ is an empirical fit within a candidate grid, not a formula anyone can point to and say *this is why 0.9 is correct*. It is a tuning standard, not a modeling claim, and is expected to be revisited mainly if the grid search itself becomes a compute bottleneck.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Service-level target consumed by the ordering rule | $\alpha$ | `src/blueberries_voi/controller/rung0.py:60` (`CorrectedAgeBlindPolicy.__init__`, default `alpha: float = 0.9`) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Rust) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `crates/voi_core/src/policy.rs:143` ([`protection_demand_quantile`](/api/rust/voi_core/policy/fn.protection_demand_quantile.html)) |
| Order rule consuming $\alpha$ to produce $q_t$ (Rust) | $q_t$ | `crates/voi_core/src/policy.rs:246` ([`damped_sw_order_f_belief`](/api/rust/voi_core/policy/fn.damped_sw_order_f_belief.html)) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Python mirror) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `src/blueberries_voi/model/demand_fractile.py:91` (`protection_interval_quantile`) |
| Grid search that picks $\alpha^\star$ by simulated profit | $\alpha^\star = \arg\max_\alpha \mathbb{E}[\text{profit}]$ | `src/blueberries_voi/sim/alpha_tune.py:493` (`tune_alpha_grid`) |
| Candidate grid used for tuning | grid $= \{0.5,\dots,0.95\}$ | `src/blueberries_voi/sim/alpha_tune.py:72` (`DEFAULT_DESKTOP_ALPHAS`) |
| Saved tuned-$\alpha$ table (per policy arm, most recent regeneration) | — | `experiments/tuned_alpha.json` (`rung0`: 0.95, `sw`: 0.9999, `dp`: 0.9, `constant`: 0.5; `rollout` inherits the `sw` value rather than being independently tuned) |

## Caveats

- $\alpha$ is tuned *per policy arm*, not once globally: the checked-in table shows different arms landing on different values (e.g., 0.9999 for the survival-weighted arm and 0.95 for `rung0` versus 0.5 for the constant-order baseline), so "the tuned $\alpha$" is not a single universal number. The 0.9 seen as a default in several code paths is a fallback, not necessarily any given arm's tuned optimum.
- The grid search only evaluates the specific candidate values in the grid (0.5 to 0.95 in the desktop grid; a smaller grid in CI). It is not a continuous optimization, so the reported $\alpha^\star$ is the best of a finite set, not a guaranteed global optimum.
- The profit costs used elsewhere in this project's simulations (`unit_margin`, `waste_cost`, `stockout_penalty`) are an uncalibrated scaffold, not fitted blueberry-store economics — so even the theoretical fractile this page argues against would, today, be computed from made-up costs rather than real ones. That's a separate problem from the one this page addresses, but it means "tuned by simulated profit" is only as trustworthy as the profit model driving the simulation.
