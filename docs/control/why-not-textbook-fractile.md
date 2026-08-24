---
title: Why not the textbook fractile
sources:
  adr: [0060]
  code: [crates/voi_core/src/policy.rs, src/blueberries_voi/model/demand_fractile.py, src/blueberries_voi/controller/rung0.py, src/blueberries_voi/sim/alpha_tune.py]
---

# Why not the textbook fractile

The [previous page](/control/newsvendor) derived a clean formula for the best order quantity: order up to the $\frac{c_u}{c_u+c_o}$ quantile of demand. This project's ordering rule still orders up to *some* quantile of demand — but that quantile, called $\alpha$, is not computed from that formula. It's a **tuned service-level target** (0.9 by default) chosen by running simulated episodes and seeing which value produces the most profit. This page explains why.

> **Figure (coming soon):** a line chart of simulated episode profit against a grid of candidate $\alpha$ values (0.5 through 0.95) for one policy arm, with the peak marked — showing $\alpha$ chosen by search rather than by formula.

## The idea

The textbook fractile $\frac{c_u}{c_u+c_o}$ is the right answer to a specific question: "if every leftover unit is destroyed at the end of the period, what's the best order quantity?" But that's not the situation on the shelf here. A punnet of blueberries that doesn't sell today usually isn't thrown out today — it's still there tomorrow, a bit less fresh, available to be sold or to spoil on some later day. Inventory *carries over*, and it carries over as fruit that keeps aging rather than as fruit that resets.

That breaks the assumption the textbook formula depends on. The real cost of an "extra" unit ordered today isn't simply "this unit is wasted" — it's some mix of a small holding cost and a chance that the unit spoils *later*, and that chance depends on how the whole multi-day ordering policy behaves from here on: how aggressively future days re-order, how the fruit already on the shelf gets picked versus left behind, and so on. There's no way to write that down as a clean, fixed number the way $c_o$ is fixed in the one-shot problem — it's entangled with the policy itself. Rather than trying to derive a corrected formula for it, this project sidesteps the derivation: it runs the full closed-loop system under a range of candidate $\alpha$ values and simply keeps whichever one comes out most profitable in simulation.

## The math

The ordering rule (see [the ordering rule page](/control/ordering-rule) for the full picture) has the shape

$$
q_t = \text{caseRound}\!\left(\big[F^{-1}_{D_{t:t+L}}(\alpha) - \tilde I_t\big]^+\right)
$$

where $D_{t:t+L}$ is demand over the protection interval (the days a new order must cover before the next order can arrive), $F^{-1}_{D_{t:t+L}}(\alpha)$ is the $\alpha$-quantile of that demand — structurally the same inverse-CDF quantity as $q^*$ on the newsvendor page — $\tilde I_t$ is effective inventory already on hand (see [Effective inventory](/control/effective-inventory)), $(\,\cdot\,)^+$ is $\max(\cdot, 0)$, and $\text{caseRound}$ rounds to the nearest case pack.

The difference from the textbook page is entirely in how $\alpha$ is chosen. There, $\alpha = \frac{c_u}{c_u+c_o}$, computed once from two fixed costs. Here, $\alpha$ is picked by grid search: for a set of candidate values $\{0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95\}$, the full closed-loop system — controller, filter, arrivals, demand, everything — is simulated end to end for each candidate, and the $\alpha$ that yields the highest simulated episode profit is kept:

$$
\alpha^\star = \arg\max_{\alpha \,\in\, \text{grid}} \ \mathbb{E}\big[\text{episode profit} \mid \alpha\big]
$$

where the expectation is estimated by running scored simulation days under shared random numbers across candidates (so the comparison isn't just noise). This is a search over outcomes, not a derivation from costs — nothing here claims to solve for $\alpha^\star$ in closed form.

## Why it's modelled this way

ADR 0060 (`CTL-03`) frames the problem directly: a leftover unit here is usually sold tomorrow, so the true overage cost is closer to $h + c_w \cdot P(\text{outdates before selling})$ — a holding cost $h$ plus a waste cost $c_w$ weighted by the *policy-dependent* probability that the unit eventually spoils before it sells — and that probability isn't something the closed-form newsvendor derivation can produce, because it depends on the ordering policy's own future behavior. Two alternatives were on the table:

- **Theoretical fractile ($c_u/(c_u+c_o)$ as-is)** — rejected as simply the wrong answer to this problem: it assumes leftovers are destroyed, which isn't true here.
- **Report both, side by side** (the recommendation on the decision card, not what was chosen) — would have shown the theoretical fractile next to the tuned one as a small comparison figure, gap as a function of the demand's variance-to-mean ratio.

The decision taken instead — **tuned by simulation**, chosen against the card's own recommendation — is justified in the ADR as recovering a known correction (the Nahmias 1976 / Nandakumar & Morton 1993 result that perishable-inventory service levels should sit above the naive newsvendor fractile) empirically, without having to re-derive it. The ADR also ties this to fairness across the project's comparison ladder: every policy arm compared in this project's evaluations is required to use its own tuned $\alpha$, specifically because an *untuned* baseline is flagged in the ADR's own notes as "the easiest way to manufacture an impressive and worthless number" — i.e., a strawman comparison would quietly cripple one arm just by leaving its $\alpha$ un-tuned.

**Honest caveat, from the ADR itself:** this is a deliberate, called-out override of the recommended approach (marked ⚑ in the ADR), and it comes with real cost — the tuned $\alpha$ is an empirical fit within a candidate grid, not a formula anyone can point to and say *this is why 0.9 is correct*. The ADR explicitly does not expect this to be revisited except if the grid search itself becomes a compute bottleneck; it is a tuning standard, not a modeling claim.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Service-level target consumed by the ordering rule | $\alpha$ | `src/blueberries_voi/controller/rung0.py:60` (`CorrectedAgeBlindPolicy.__init__`, default `alpha: float = 0.9`) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Rust) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `crates/voi_core/src/policy.rs:111` ([`protection_demand_quantile`](/api/rust/voi_core/policy/fn.protection_demand_quantile.html)) |
| Order rule consuming $\alpha$ to produce $q_t$ (Rust) | $q_t$ | `crates/voi_core/src/policy.rs:201` ([`damped_sw_order_f_belief`](/api/rust/voi_core/policy/fn.damped_sw_order_f_belief.html)) |
| Protection-interval demand quantile $F^{-1}(\alpha)$ (Python mirror) | $F^{-1}_{D_{t:t+L}}(\alpha)$ | `src/blueberries_voi/model/demand_fractile.py:91` (`protection_interval_quantile`) |
| Grid search that picks $\alpha^\star$ by simulated profit | $\alpha^\star = \arg\max_\alpha \mathbb{E}[\text{profit}]$ | `src/blueberries_voi/sim/alpha_tune.py:481` (`tune_alpha_grid`) |
| Candidate grid used for tuning | grid $= \{0.5,\dots,0.95\}$ | `src/blueberries_voi/sim/alpha_tune.py:65` (`DEFAULT_DESKTOP_ALPHAS`) |
| Saved tuned-$\alpha$ table (per policy arm, most recent regeneration) | — | `experiments/tuned_alpha.json` (`rung0`: 0.95, `sw`: 0.95, `dp`: 0.9, `constant`: 0.5; `rollout` inherits the `sw` value rather than being independently tuned) |

## Caveats

- $\alpha$ is tuned *per policy arm*, not once globally: the checked-in table shows different arms landing on different values (e.g., 0.95 for the survival-weighted and Rung-0 arms versus 0.5 for the constant-order baseline), so "the tuned $\alpha$" is not a single universal number — the 0.9 seen as a default in several code paths is a fallback, not necessarily any given arm's tuned optimum.
- The grid search only evaluates the specific candidate values in the grid (0.5 to 0.95 in the desktop grid; a smaller grid in CI) — it is not a continuous optimization, so the reported $\alpha^\star$ is the best of a finite set, not a guaranteed global optimum.
- The profit costs used elsewhere in this project's simulations (`unit_margin`, `waste_cost`, `stockout_penalty`) are explicitly documented as an uncalibrated scaffold, not fitted blueberry-store economics — so even the theoretical fractile this page argues against would, today, be computed from made-up costs rather than real ones. That's a separate problem from the one this page addresses, but it means "tuned by simulated profit" is itself only as trustworthy as the profit model driving the simulation.
