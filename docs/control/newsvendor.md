---
title: The newsvendor problem
sources:
  adr: []
  code: []
---

# The newsvendor problem

Before getting into how this project decides how many blueberries to order, it helps to see the classical puzzle every inventory-ordering system is compared against. The **newsvendor problem** asks: given uncertain demand and a cost for guessing too low versus too high, what's the single best order quantity? It's a long-standing piece of operations research, and it's the vocabulary — "critical fractile," "underage cost," "overage cost" — that later pages in this section borrow, even where this project ultimately does something different with it.

> **Figure (coming soon):** a demand probability curve with the area to the left of the order quantity $q$ shaded to represent the overage region and the area to the right shaded for the underage region, showing how tilting $q$ trades one area for the other.

## The idea

Picture a newspaper vendor who has to decide, before dawn, how many papers to buy for the day. Buy too few, and they miss sales they could have made — each unmet copy is a small loss. Buy too many, and the leftover papers are worthless once the day is over — each excess copy is also a small loss. The vendor doesn't know exactly how many customers will show up; they only know roughly what a normal day looks like.

The trick is that the vendor doesn't need to predict demand exactly — they need to pick the order quantity that best balances the two *kinds* of mistake, given how expensive each kind is. If running out is much more painful than being stuck with extra stock, the vendor should deliberately over-order, aiming to satisfy demand almost all the time. If leftover stock is the more painful mistake, they should deliberately under-order and accept running out somewhat often. The exact best trade-off point turns out to depend only on the *ratio* of the two costs, not on their absolute size — which is what makes the problem tractable.

## The math

Let $D$ be demand for the period — a random quantity, not known when the order is placed. The order quantity $q$ must be chosen before $D$ is observed. Two costs govern the trade-off:

- $c_u$, the **underage cost**: the cost incurred per unit of demand that goes unmet because $q$ was too low (e.g., lost profit margin on a missed sale).
- $c_o$, the **overage cost**: the cost incurred per unit of leftover stock because $q$ was too high (e.g., the cost of stock that must be discarded at the end of the period).

Expected total cost, as a function of the chosen $q$, is

$$
C(q) = c_u \, \mathbb{E}\big[(D - q)^+\big] + c_o \, \mathbb{E}\big[(q - D)^+\big]
$$

where $(x)^+ = \max(x, 0)$. The first term is the expected shortfall cost (demand exceeding what was ordered); the second is the expected leftover cost (order exceeding demand). $C(q)$ is convex in $q$, so it has a single minimum, and standard calculus (differentiate, set to zero) gives the optimum in closed form. Writing $F$ for the cumulative distribution function of demand $D$ — so $F(x) = P(D \le x)$ — the optimal order quantity is

$$
q^* = F^{-1}\!\left(\frac{c_u}{c_u + c_o}\right)
$$

The quantity $\dfrac{c_u}{c_u + c_o}$ is called the **critical fractile**: a number between 0 and 1 saying what quantile of the demand distribution to order up to. $F^{-1}$ is the inverse CDF (the quantile function) of demand — so $q^*$ is "the demand level such that a fraction $\frac{c_u}{c_u+c_o}$ of possible demand outcomes fall at or below it." If underage is twice as costly as overage, the critical fractile is $\frac{2}{3}$, and the vendor should order enough to cover demand in two-thirds of possible scenarios — deliberately accepting a shortfall the other third of the time, because chasing full coverage would mean eating too much overage cost.

## Why it's modelled this way

The newsvendor formulation is deliberately the simplest possible version of "order under uncertainty, pay for guessing wrong in either direction." It assumes exactly **one order, one period, one demand draw** — the vendor buys once, sells (or doesn't) during the period, and any unsold stock is destroyed or otherwise loses essentially all its value at period end. That single-period, single-decision structure is precisely what makes the closed-form answer above possible: there's no future period for a leftover unit to be carried into, so its cost is cleanly "wasted," full stop.

That simplicity is also the honest limitation. Real inventory systems usually don't throw away every leftover unit at a hard boundary — and the system this project models is one of those: fruit that isn't sold today is not gone, it's still on the shelf tomorrow, a little less fresh. **This project does not use the textbook critical fractile directly** — the next page, [Why not the textbook fractile](/control/why-not-textbook-fractile), explains why the one-shot assumption above breaks down once leftover stock carries over and ages instead of vanishing.

## Caveats

- This page describes the classical, generic newsvendor model as it appears in any standard operations-research treatment — it is not sourced from this repository's code or ADRs, and nothing on this page is a claim about how the current controller actually orders.
- The clean closed-form solution above relies on the single-period, "leftovers are destroyed" assumption; it is a baseline to reason from, not a policy this project deploys as-is.
