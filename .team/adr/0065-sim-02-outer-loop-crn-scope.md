# 0065. SIM-02: Outer-loop CRN scope
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-02
GROUP: SIM
PROVENANCE: notes-agree
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Milestone: M3. Generalises [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)'s within-rollout
CRN requirement to the outer loop that actually produces the VOI numbers.*

**The question.**

[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) already established, for the rollout's inner
candidate comparison, that independent sampling makes a real ~0.5% signal indistinguishable from ~30%
per-path noise, and that pairing (CRN) is what rescues it — variance ratio ~1800 in the worked example.
**The exact same argument applies one level up**, to the comparison that actually produces the
project's headline numbers: constant-order vs Rung 0 vs survival-weighted vs +rollout, across every
knowledge scenario and every β in the sweep. If those are evaluated independently, the VOI numbers
inherit the same signal-to-noise problem rollout was built to avoid, just at a different layer.

**Why C is not just "more of the same," but actually cheaper to reason about.**

Different knowledge scenarios ([SCN-P0](SCN-P0%20Books%20only.md) through
[SCN-F2a](SCN-F2a%20Pack%20date%20on%20the%20supplier%20ASN.md)) differ only in **what a policy is
allowed to observe**, not in the underlying physical process — demand realises the same way, lots
arrive at the same true ages, units spoil on the same flips, regardless of whether the policy gets to
see any of it. That means the *same* underlying realization is valid to reuse across every scenario at
a fixed β: scenario becomes a filter over what's revealed, layered on top of one shared truth. This is
a stronger and cheaper form of CRN than rollout's, because rollout only pairs across *candidates*;
here the same principle also pairs across the *entire knowledge ladder*, which is the actual axis the
VOI sweep reports.

## Decision

We will adopt **C — Full CRN -- one shared physical realization per (beta, replication) across every knowledge scenario and every policy**.

**C — Full CRN -- one shared physical realization per (beta, replication) across every knowledge scenario and every policy.** Different scenarios differ only in what is observed, not in the underlying truth, so the same draws are valid to reuse everywhere. Requires the semantic-slot RNG scheme (SIM-05) to be built once and used project-wide.

## Alternatives considered

- **A — No CRN across the outer VOI loop -- each (scenario, beta, policy, replication) draws fresh randomness** — not chosen. Simplest, but stacks the same signal-to-noise problem CTL-02 already solved for rollout onto the policy-comparison layer.
- **B — CRN across policies within a knowledge-scenario x beta arm** — not chosen. Same demand/spoilage/arrival realization compared across baselines and the shipped policy, independent across scenario/beta arms.

## Consequences

Different scenarios differ only in what is observed, not in the underlying truth, so the same draws are valid to reuse everywhere. Requires the semantic-slot RNG scheme (SIM-05) to be built once and used project-wide.

**What this gates:** [SIM-05](SIM-05%20Seed%20and%20experiment%20addressing%20scheme.md)'s scope — whether it needs to be a
project-wide semantic-slot scheme or can stay local to the rollout's candidate loop. Also gates the
reporting standard: paired bootstrap CIs on VOI, matching
[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)'s existing requirement for paired intervals on
policy comparisons.

**Revisit if:** The full-CRN scheme turns out to be a larger engineering lift than expected (e.g. the filter's
particle resampling makes exact pairing across scenario arms awkward) — fall back to B and accept
noisier point-to-point comparisons on the VOI surface.

**Depends on:** `CTL-02`, `X-06`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
