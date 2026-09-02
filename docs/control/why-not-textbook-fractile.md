---
title: Why not the textbook fractile
sources:
  code: [crates/voi_core/src/policy.rs, src/blueberries_voi/model/demand_fractile.py, src/blueberries_voi/controller/rung0.py, src/blueberries_voi/sim/alpha_tune.py]
---

# Why not the textbook fractile

The [previous page](/control/newsvendor) derived a clean formula for the best order quantity: order up to the $\frac{c_u}{c_u+c_o}$ quantile of demand. This project's ordering rule still orders up to *some* quantile of demand — but that quantile, called $\alpha$, isn't computed from that formula. It's a tuned service-level target (0.9 by default, before tuning) chosen by simulating the whole system and seeing which value produces the most profit. This page explains why.

## The idea

The textbook fractile $\frac{c_u}{c_u+c_o}$ answers a specific question: if every leftover unit is thrown away at the end of the period, what's the best order quantity? That's not the situation on the shelf here. A punnet of blueberries that doesn't sell today isn't thrown out — it's still there tomorrow, a little less fresh, available to sell or to spoil on some later day. Inventory carries over and keeps losing freshness rather than resetting.

That breaks the assumption the textbook formula depends on. The real cost of an "extra" unit ordered today is some mix of a small holding cost and a chance the unit spoils later — and that chance depends on how the whole multi-day ordering policy behaves from here on: how aggressively future days re-order, how fruit already on the shelf gets picked versus left behind. There's no way to write that down as a clean, fixed number the way $c_o$ is fixed in the one-shot textbook problem; it's tangled up with the policy itself. Rather than deriving a corrected formula by hand, this project sidesteps the derivation: it runs the full closed-loop system under a range of candidate $\alpha$ values and keeps whichever one comes out most profitable in simulation.

## The math

The ordering rule (see [the ordering rule page](/control/ordering-rule) for the full picture) has the shape

$$
q_t = \text{caseRound}\!\left(\big[F^{-1}_{D_{t:t+L}}(\alpha) - \tilde I_t\big]^+\right)
$$

where $D_{t:t+L}$ is demand over the protection interval (the days a new order must cover before the next order can arrive), $F^{-1}_{D_{t:t+L}}(\alpha)$ is the $\alpha$-quantile of that demand — structurally the same inverse-CDF quantity as $q^*$ on the newsvendor page — $\tilde I_t$ is effective inventory already on hand (see [Effective inventory](/control/effective-inventory)), $(\,\cdot\,)^+$ means "take the larger of this and zero," and $\text{caseRound}$ rounds to the nearest case pack.

The difference from the textbook page is entirely in how $\alpha$ is chosen. There, $\alpha = \frac{c_u}{c_u+c_o}$, computed once from two fixed costs. Here, $\alpha$ is found by search rather than by formula: the full closed-loop system — controller, filter, arrivals, demand — is simulated end to end for many candidate values, and the value that yields the highest simulated profit is kept:

$$
\alpha^\star = \arg\max_{\alpha} \ \mathbb{E}\big[\text{episode profit} \mid \alpha\big]
$$

In the experiments behind this project's published results, that search is a joint Bayesian Optimization (BO) — an algorithm that picks each next candidate to try based on what previous trials revealed, rather than trying every value on a fixed list — over $\alpha \in [0.1, 0.9999]$ together with a related tuning knob, $\rho$, run separately for each observation scenario with 25 trial evaluations per scenario across a pool of 30 seeds. The expectation in the formula above is estimated by running simulated days under matched random draws across candidates, so that differences in the outcome reflect the candidate's quality rather than noise. This is a search over outcomes, not a derivation from costs — nothing here claims to solve for $\alpha^\star$ in closed form.

An earlier version of this project tuned $\alpha$ with a simpler mechanism — a plain grid search over a short, fixed list of candidate values — before the joint Bayesian Optimization search above became the source of the published results. That earlier mechanism is still in the codebase (see the table below) but no longer produces the numbers reported elsewhere on this site.

## Why it's modelled this way

A leftover unit here is usually sold tomorrow, so the true overage cost is closer to $h + c_w \cdot P(\text{spoils before selling})$ — a holding cost $h$ plus a waste cost $c_w$, weighted by the policy-dependent probability that the unit eventually spoils before it sells. That probability isn't something the closed-form newsvendor derivation can produce, because it depends on the ordering policy's own future behavior. Reporting the theoretical fractile as-is would be the wrong answer to this problem, since it assumes leftovers are destroyed, which isn't true here.

Tuning $\alpha$ by simulation recovers, empirically, a correction that the perishable-inventory literature derives analytically: service levels for perishable goods should sit above the naive newsvendor fractile (Nahmias 1976; Nandakumar & Morton 1993). Doing it by simulation avoids re-deriving that correction from scratch for this project's specific dynamics. Every ordering policy compared in this project's evaluations gets its own tuned $\alpha$ — leaving one policy's $\alpha$ untuned would unfairly stack the comparison against it.

**Honest caveat.** The tuned $\alpha$ is an empirical fit, not a formula anyone can point to and say *this is why 0.9 is correct*. It's a practical tuning standard, not a claim about the underlying model.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Service-level target consumed by the ordering rule (the service-level policy, `rung0`) | $\alpha$ | `src/blueberries_voi/controller/rung0.py:60` (`CorrectedAgeBlindPolicy.__init__`, default `alpha: float = 0.9`) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Rust) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `crates/voi_core/src/policy.rs:143` ([`protection_demand_quantile`](/api/rust/voi_core/policy/fn.protection_demand_quantile.html)) |
| Order rule consuming $\alpha$ to produce $q_t$ (Rust) | $q_t$ | `crates/voi_core/src/policy.rs:246` ([`damped_sw_order_f_belief`](/api/rust/voi_core/policy/fn.damped_sw_order_f_belief.html)) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Python mirror) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `src/blueberries_voi/model/demand_fractile.py:91` (`protection_interval_quantile`) |
| Earlier, now-superseded grid-search mechanism for picking $\alpha^\star$ by simulated profit | $\alpha^\star = \arg\max_\alpha \mathbb{E}[\text{profit}]$ | `src/blueberries_voi/sim/alpha_tune.py:493` (`tune_alpha_grid`) |
| Earlier, now-superseded candidate grid | grid $= \{0.5,\dots,0.95\}$ | `src/blueberries_voi/sim/alpha_tune.py:72` (`DEFAULT_DESKTOP_ALPHAS`) |
| Tuned $\alpha$ values saved in the project, by policy | — | `experiments/tuned_alpha.json` — service-level policy (`rung0`): 0.95; survival-weighted policy (`sw`): 0.9999; dynamic-program policy (`dp`): 0.9; constant-order baseline (`constant`): 0.5; rollout-based policy (`rollout`) inherits the survival-weighted policy's value rather than being tuned independently |

## Caveats

- $\alpha$ is tuned *per policy*, not once globally: the table saved in the project shows different policies landing on different values — 0.95 for the service-level policy, 0.9999 for the survival-weighted policy, 0.9 for the dynamic-program policy, and 0.5 for the constant-order baseline — so "the tuned $\alpha$" isn't a single universal number. The 0.9 seen as a default in the code is a fallback value, not necessarily any given policy's tuned optimum.
- The search only evaluates a finite number of trials (25 per scenario in the Bayesian Optimization search; a fixed short list in the older grid-search mechanism). Neither is a continuous, exhaustive optimization, so the reported $\alpha^\star$ is the best result found, not a guaranteed global optimum.
- This project's profit costs (unit margin, waste cost, stockout penalty) are a deliberate synthetic design, not figures fitted to a real store: sell price $4.50/unit, purchase cost $1.80/unit (margin $2.70/sale), waste cost $1.20/unit, and a stockout penalty of $2.50/lost sale, for an effective stockout cost of about $5.20 once forgone margin is included — roughly 4.3 times the cost of wasting a spoiled unit. That asymmetry is intentional, but the costs still haven't been validated against a real store, so "tuned by simulated profit" is only as trustworthy as this profit model.
