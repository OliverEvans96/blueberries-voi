# 0066. SIM-03: Episode structure and burn-in
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-03
GROUP: SIM
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Milestone: M3.*

**The question.**

The controller note's Rung 0 baseline is only well-posed because "the stationary age distribution
exists as a single object" under i.i.d. demand and daily delivery
([X-11](X-11%20Delivery%20cadence%20for%20the%20base%20case.md)). That baseline, and the whole
comparison built on top of it, implicitly assumes the simulator is being evaluated *in* that stationary
regime — not during the transient while the shelf fills up from empty. Nothing has yet decided how
episodes are structured to guarantee that.

There's a second reason this isn't free to ignore:
[MOD-13](MOD-13%20Bounding%20the%20number%20of%20live%20cohorts.md) lets cohorts run to extinction with
no cap, and under LIFO-ish picking old cohorts linger. The live-cohort count and the age composition
both take some number of days to reach their steady-state behaviour from a cold start, and recording
profit before that point mixes "genuine policy performance" with "artifact of starting from an
unrealistic empty shelf."

## Decision

We will adopt **A — One long trajectory per replication, discard an initial burn-in before recording profit**.

**A — One long trajectory per replication, discard an initial burn-in before recording profit.** Reaches the genuine stationary age distribution the Rung-0 baseline (CTL-05) assumes exists.

## Alternatives considered

- **B — Many independent short episodes, record from day 1, fixed or randomized start** — not chosen. Simpler bookkeeping, but every episode's early days are a startup transient, not steady state.
- **C — One long trajectory, no burn-in, record everything from day 1** — not chosen. Cheapest, confounds genuine VOI with the one-time cost of reaching steady state.

## Consequences

Reaches the genuine stationary age distribution the Rung-0 baseline (CTL-05) assumes exists.

**What this gates:** The burn-in length becomes a parameter reported alongside $H$ and $M$ in the appendix. Also affects
compute cost — burn-in days are simulated but not scored, adding to the total cost of the VOI sweep
already dominated by rollout ([CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)).

**Revisit if:** The live-cohort-count or age-composition distributions don't visibly plateau within a reasonable
burn-in window — that would itself be a notable finding (per CLAUDE.md's own flag on watching the cost
of the coarse-grid filter choice) and might mean the system doesn't have a clean stationary regime at
all under some parameter settings.

**Depends on:** `X-11`, `MOD-13`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
