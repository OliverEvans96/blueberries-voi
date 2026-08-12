# 0071. VOI-03: Statistical reporting standard
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI-03
GROUP: VOI
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Milestone: M3. Follows directly from a rule already stated for the rollout's inner loop
([CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)) and now extended by
[SIM-02](SIM-02%20Outer-loop%20CRN%20scope.md) to the outer VOI comparison — this card is about what
gets *reported*, given that machinery.*

**The question.**

[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) already states the rule for policy comparisons
inside the rollout: "every interval on a policy comparison must be paired — bootstrap the per-path
differences, never a two-sample interval on the two means. A two-sample interval discards exactly the
correlation you engineered and will make real differences look insignificant." Once
[SIM-02](SIM-02%20Outer-loop%20CRN%20scope.md) extends CRN pairing to the whole VOI sweep, the same
logic applies to *every number the post reports* — the question here is simply how much of that
statistical picture actually appears in the writeup, not the underlying analysis.

## Decision

We will adopt **B — Point estimate plus paired bootstrap CI per arm**.

**B — Point estimate plus paired bootstrap CI per arm.** Direct continuation of CTL-02's "every interval on a policy comparison must be paired" requirement, applied to the outer VOI loop.

## Alternatives considered

- **A — Point estimates only -- mean VOI per arm** — not chosen. What the CRN infrastructure is built for but doesn't require reporting; understates how much confidence to place in each number.
- **C — Full distribution shown -- e.g. violin or histogram of the paired bootstrap differences** — not chosen. Richest picture, most figure-design work, and arguably more detail than a blog-post reader needs per comparison.

## Consequences

Direct continuation of CTL-02's "every interval on a policy comparison must be paired" requirement, applied to the outer VOI loop.

**What this gates:** The output format of the VOI sweep code — every arm needs to retain its paired bootstrap replicates,
not just a summary mean, which is a data-pipeline decision worth fixing before the sweep is written
rather than after.

**Revisit if:** A specific comparison's CI turns out surprisingly wide even with full CRN pairing — that's worth a
distributional figure (C) for that one cell specifically, as a diagnostic rather than a reporting
default.

**Depends on:** `CTL-02`, `SIM-02`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
