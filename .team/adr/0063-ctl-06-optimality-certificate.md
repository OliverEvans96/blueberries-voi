# 0063. CTL-06: Optimality certificate
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-06
GROUP: CTL
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2. Named as a separate card from
[CTL-05](CTL-05%20Baseline%20ladder.md) because whether to build it is a real decision on its own,
even though it also appears as the fifth rung of that ladder.*

**The question.**

Rollout guarantees $J_{\tilde\pi}\ge J_\pi$ — never worse than the base policy — but that's a
statement about improvement, not about closeness to optimal. Without an independent ground truth,
"the shipped policy is good" and "the shipped policy is 1% off optimal" are indistinguishable claims
that happen to produce the same headline number. The AI notes call this exact-DP-at-toy-scale
certificate "the most valuable non-headline experiment in the project" for a specific reason: it's
what tells a reader whether a claimed VOI of a few percent is a real effect or noise from an
under-improved policy.

**The trap to watch.**

The β=1 check inside this certificate only passes if the age-aware policy and Rung 0 use the *same*
protection interval $\Delta\tau_L$. Under the daily-delivery base case
([X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md)) that's automatic; under any other cadence it
isn't, and a mismatched window would fail the check for a calendar reason unrelated to age
information. Assert $\Delta\tau_L$ equality in the test rather than assuming it.

## Decision

We will adopt **A — Build it — toy-scale exact DP, report the gap**.

**A — Build it — toy-scale exact DP, report the gap.** Small demand, truncated tau_max, ~2 lots. Backward induction is tractable at this scale.

## Alternatives considered

- **B — Skip it — trust CTL-02's rollout guarantee alone** — not chosen. J improves monotonically over the base policy, but that says nothing about distance from optimal.

## Consequences

Small demand, truncated tau_max, ~2 lots. Backward induction is tractable at this scale.

**What this gates:** Directly adjudicates whether [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)'s "single-step
rollout is enough" needs revisiting, per that card's decision rule.

**Revisit if:** N/A — this card's outcome is itself the trigger for other decisions, not something to be revisited by
an external event.

**Depends on:** `CTL-01`, `CTL-02`, `X-07`

**Milestone:** M2 — controller and multi-scenario
