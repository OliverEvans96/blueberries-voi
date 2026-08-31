---
title: The ordering rule
sources:
  code: [crates/voi_core/src/policy.rs, crates/voi_core/src/voi.rs, crates/voi_core/src/rollout.rs, crates/voi_core/src/params.rs, src/blueberries_voi/controller/f_sw.py, src/blueberries_voi/sim/bakeoff_ordering.py, src/blueberries_voi/sim/alpha_tune.py]
---

# The ordering rule

This is the formula that turns everything else on this site — the demand model, the freshness belief, the delivery calendar — into a single number each order day: how many units to order. It's a **damped, survival-weighted base-stock rule**: order enough to close most (not all) of the gap between a demand target and what's already effectively on hand, then round to a full case.

## The idea

On each day the store is allowed to place an order, the policy asks two questions: "how much demand do I need to survive until I can order again?" (see [Protection demand](/control/protection-demand)) and "how much protection do I already have on the shelf and in transit?" (see [Effective inventory](/control/effective-inventory)). The gap between those two numbers is, roughly, how much more stock is needed.

But closing that whole gap in one order turns out to be a mistake. A plain base-stock rule — order exactly enough to top up to the target every time — reacts too strongly to how much is already on hand: for every extra unit sitting on the shelf, it orders exactly one fewer unit. That's a sharper reaction than this problem's dynamics call for, given positive lead time and fruit that decays rather than staying pristine forever. So the rule **damps** its response: instead of closing the whole gap, it closes a fixed fraction $\rho$ of it (by default, 80%). Finally, because a store can't order half a case, the raw damped quantity is rounded to the nearest multiple of the case size — which can swallow a small gap into a full extra case, or drop it to zero, as happens for a raw gap of 0.55 units against a case size of 8.

## The math

$$
q = \text{caseRound}\Big(\rho \, \big[F^{-1}_{D}(\alpha) - \tilde I\big]^+\Big)
$$

where:

- $q$ is the order quantity, in units, already rounded to a case multiple.
- $F^{-1}_{D}(\alpha)$ is the $\alpha$-quantile of total demand $D$ over the protection window — see [Protection demand](/control/protection-demand) for how this is computed under the delivery calendar.
- $\tilde I$ is effective inventory, the quality-weighted stock already on hand plus pipeline — see [Effective inventory](/control/effective-inventory).
- $[\,\cdot\,]^+$ means $\max(\cdot, 0)$: never order a negative amount.
- $\rho > 0$ scales how much of the order gap is closed before case-rounding. Values in $(0, 1]$ are the classical **damping** interpretation (partial gap closure; Nahmias); $\rho > 1$ over-closes the gap (more aggressive ordering) and is allowed in Studio and Ax tuning up to $2$. Default: $0.8$.
- $\text{caseRound}(x) = \big\lfloor x / c + 0.5 \big\rfloor \cdot c$ rounds to the **nearest** multiple of the case size $c$ (ties round away from zero), not up or down.

**Worked example**, continuing the effective-inventory page's numbers: with $\tilde I = 18$ and a 3-day protection window ($F^{-1}_{D}(0.9) \approx 107$ units, under the default demand parameters — see [Protection demand](/control/protection-demand) for how that number is produced), the raw damped gap is $\rho \, [107 - 18]^+ = 0.8 \times 89 = 71.2$. Case-rounded to a case size of 8, that becomes $\text{caseRound}(71.2) = 72$ units.

## Why it's modelled this way

This project uses a **damped survival-weighted base-stock** rule rather than an undamped one. Under proportional decay with zero lead time, a classical result (Van Zyl / Veinott, 1965) shows plain base-stock policies are exactly optimal — but this project's dynamics deviate from that ideal case in the two ways the whole project is about: decay isn't perfectly proportional, and lead time is positive, not zero. Plain base-stock has a known weak spot here: it has $\partial q/\partial x = -1$ exactly (order one fewer unit for every extra unit on hand), while the true optimum under this project's dynamics is a strictly muted response, $-1 < y' \le 0$. Nahmias (1975b) found that a damped correction performs comparably to the best "critical number" policy and should help further under parameter uncertainty — exactly the situation this project is in, since decay and lead time here aren't the textbook zero-lead-time, proportional-decay case.

Plain base-stock with raw (age-blind) unit counts was considered and rejected outright — it just counts units on hand, ignoring freshness entirely. An undamped, survival-weighted base-stock rule was also considered but not adopted, in favor of the damped version described here.

**Honest caveat.** The damping factor $\rho = 0.8$ is not derived from this project's specific cost structure; it's a general correction borrowed from the Nahmias literature, applied as one extra scalar rather than re-derived from scratch for this problem.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Order quantity (Rust) | $q$ | `crates/voi_core/src/policy.rs:246` ([`damped_sw_order_f_belief`](/api/rust/voi_core/policy/fn.damped_sw_order_f_belief.html)) |
| Order quantity (Python) | $q$ | `src/blueberries_voi/controller/f_sw.py:20` (`damped_sw_order_f_belief`) |
| Damped gap before case-rounding | $\rho\,[F^{-1}_D(\alpha) - \tilde I]^+$ | `crates/voi_core/src/policy.rs:272` (`raw = rho * (d_star - i_tilde).max(0.0)`) |
| Damping factor, default value | $\rho = 0.8$ | `crates/voi_core/src/session.rs:1033` (`rho.unwrap_or(0.8)`) and `crates/voi_core/src/voi.rs:290` (call-site literal); `src/blueberries_voi/sim/alpha_tune.py:83` (`_DEFAULT_RHO`) |
| Case rounding, nearest multiple | $\text{caseRound}$ | `crates/voi_core/src/policy.rs:93` ([`case_round`](/api/rust/voi_core/policy/fn.case_round.html)); `src/blueberries_voi/sim/bakeoff_ordering.py:23` (`case_round`) |
| Default case size | $c = 8$ | `crates/voi_core/src/params.rs:74` (`ModelParams::default`, `case_size`) |

## Caveats

- $\rho = 0.8$ ships as a fixed literal at the call sites that build production orders, not as a value tuned by grid search the way $\alpha$ is (see [Why not the textbook fractile](/control/why-not-textbook-fractile)) — the grid search over policy performance sweeps candidate $\alpha$ values only, with $\rho$ held fixed. There's no simulation evidence in this repo that $0.8$ specifically is the best damping factor for this exact problem instance, only the general Nahmias finding that damping of this kind helps.
- This page describes the **base** policy only. A separate rollout layer can wrap this base rule with a deeper multi-step search over candidate order quantities near $q$; that layer is not covered here.
- $\text{caseRound}$ rounds to the *nearest* case multiple, not always up — so the realized order can land a little under the raw computed target as well as over it, depending which side of the halfway point the raw gap falls on.
