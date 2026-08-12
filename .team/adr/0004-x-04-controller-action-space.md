# 0004. X-04: Controller action space
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-04
GROUP: X
PROVENANCE: contested
TIER: 1
AGAINST-RECOMMENDATION: true

## Context

**The question.**

[Updated Plan — Filter, Controller, and Where the Weibull Sits](../../Updated%20Plan%20%E2%80%94%20Filter%2C%20Controller%2C%20and%20Where%20the%20Weibull%20Sits.md) §A.7 restricted the policy to order
quantities. It then notes — correctly — that your own outline (Fig 7) predicts **VOI concentrates in
cull and markdown sequencing, not in ordering**, because ordering consumes the scalar effective
inventory where per-lot errors partly cancel, while sequencing consumes order statistics where
nothing cancels.

So the scope call as it stands measures the value of age information in precisely the channel where
it is smallest.

## Decision

We will adopt **A — Order quantity only**. Chosen against the card recommendation of **C — Orders first, sequencing as a second experiment**.

**A — Order quantity only.** ⚑ Against the card's recommendation (C). The AI notes' choice. Measures VOI in its weakest channel.

## Alternatives considered

- **B — Orders plus cull/markdown sequencing** — not chosen. Where the outline predicts VOI actually concentrates.
- **C — Orders first, sequencing as a second experiment** _(card recommendation; not chosen)_ — not chosen. Ship A, then add B if the build has room.

## Consequences

The AI notes' choice. Measures VOI in its weakest channel.

**What this gates:** CTL rollout cost and candidate set · VOI the magnitude of the headline number · whether
markdown/price elasticity enters at all.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The A-only VOI number comes out near zero. Then the post has no result without B, and B stops being
optional.

**Depends on:** `X-01`, `X-03`
