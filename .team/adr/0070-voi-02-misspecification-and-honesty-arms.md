# 0070. VOI-02: Misspecification and honesty arms
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI-02
GROUP: VOI
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M3. Named explicitly in [The Controller — Survival-Weighted Base-Stock with
Rollout](../../The%20Controller%20%E2%80%94%20Survival-Weighted%20Base-Stock%20with%20Rollout.md) §6 and
its own build order §8 step 7: "Honesty arms — misspecification and certainty equivalence, reported
even if unflattering."*

**The question.**

The clean (scenario × β) VOI sweep answers "does more information help." It doesn't answer the
questions a careful reader — or an Afresh applied scientist — would ask next: *does this survive when
the demand model is wrong the way real forecasts are wrong? Does rollout's optimisation-against-a-model
actually make things worse when the model itself is wrong?* Those are different questions from the
headline result, and the notes are explicit that skipping them isn't neutral — it's a choice to leave
the strongest objections unaddressed.

**Why these two arms specifically.**

**Model misspecification (β=1-inference-on-Weibull-truth).** Rollout optimises against whatever model
it's handed, so it can *amplify* model error where a cruder heuristic would absorb it. Nahmias (1982,
p.691) is cited directly: a decay-deflated critical-number policy was "very sensitive to the choice of
the decay constant" and underperformed even when handed the *exact* value. Running this arm with the
shipped rollout policy, not just the base policy, is where this risk actually bites.

**Demand misspecification.** Demand is *assumed known* throughout ([MOD-09](MOD-09%20Demand%20model.md):
"distribution known to every policy"), which the notes flag as "the strongest assumption in the
project and the one Afresh is most qualified to attack." A ±15% error in $\bar D$, and separately in
$k$, tests whether the age-information VOI survives realistic forecast error. It should partly survive
— forecast error and age error enter different terms — but "partly" needs an actual number, and the
CRN scaffolding ([SIM-02](SIM-02%20Outer-loop%20CRN%20scope.md)) makes the arm nearly free once it
exists.

## Decision

We will adopt **A — None -- the clean (scenario x beta) sweep only**. Chosen against the card recommendation of **C — B plus a certainty-equivalence arm -- posterior mean point estimate vs full posterior/rollout-over-belief**.

**A — None -- the clean (scenario x beta) sweep only.** ⚑ Against the card's recommendation (C). Cheapest, and the headline number stands undefended against the most obvious technical objections.

## Alternatives considered

- **B — Core two -- model misspecification (beta=1 inference on Weibull truth) and demand misspecification (wrong D-bar, wrong k)** — not chosen. The two arms the controller note names explicitly in its Checks section.
- **C — B plus a certainty-equivalence arm -- posterior mean point estimate vs full posterior/rollout-over-belief** _(card recommendation; not chosen)_ — not chosen. Tests whether carrying the full belief (not just its mean) through the controller is worth the engineering it costs.

## Consequences

Cheapest, and the headline number stands undefended against the most obvious technical objections.

**What this gates:** Compute budget for the final sweep — each arm multiplies the (scenario × β) grid by however many
misspecification settings are tested. Worth sizing against
[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)'s existing cost accounting (4–20 core-hours for
the clean sweep) before committing to C's full scope.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The clean sweep's compute cost alone approaches the high end of the 4–20 core-hour estimate — then
trim to B and treat certainty-equivalence as optional future work rather than risk the honesty arms
crowding out the headline result.

**Depends on:** `X-06`, `CTL-01`, `FIL-07`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
