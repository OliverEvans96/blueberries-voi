# 0072. VOI-04: Sweep resolution
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI-04
GROUP: VOI
PROVENANCE: newly-raised
TIER: 3
MILESTONE: M3 — VOI sweep, oracles, misspecification arms
AGAINST-RECOMMENDATION: true

## Context

*Milestone: M3.*

**The question.**

[X-06](X-06%20VOI%20sweep%20axes.md) fixed the sweep's *axes* (scenario × β) but not its *resolution* —
how many β values actually get run. This interacts directly with
[FIL-12](FIL-12%20Making%20the%20joint%20age%20posterior%20tractable.md)'s own open concern about grid
resolution ("sweep the grid size and show the posterior summary converging... if eight points and
sixteen points disagree materially, the grid is inside the signal") — except here the axis being
resolved is β itself, the parameter the whole project's headline claim is a function of.

**Why resolution matters more here than a typical parameter sweep.**

The project's central claim is structural, not just a single number: **VOI is zero at β=1 and
increasing in β** ([CTL-05](CTL-05%20Baseline%20ladder.md)'s β=1 degeneracy check is the free
correctness test for exactly this). A reader needs to see the *shape* of that relationship, not just
two endpoints, to be persuaded the claim is real and not an artefact of wherever the sweep happened to
sample. Cost is the constraint: every additional β value multiplies the whole (scenario × β × honesty
arms) sweep, which is already dominated by rollout compute
([CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md), 4–20 core-hours at the base resolution).

## Decision

We will adopt **B — Fine grid -- 10+ beta values for a smooth VOI-vs-beta curve**. Chosen against the card recommendation of **C — Coarse grid for the full (scenario x beta) sweep, plus one fine zoom sweep near beta=1 on the headline scenario pair only**.

**B — Fine grid -- 10+ beta values for a smooth VOI-vs-beta curve.** ⚑ Against the card's recommendation (C). The natural complement to VOI being zero at beta=1 and increasing in beta -- worth resolving the actual shape, not just the endpoints.

## Alternatives considered

- **A — Coarse grid -- 3-4 beta values spanning the plausible range, industry default beta=1 included** — not chosen. Cheapest; enough to show a trend but not enough to characterise its shape confidently.
- **C — Coarse grid for the full (scenario x beta) sweep, plus one fine zoom sweep near beta=1 on the headline scenario pair only** _(card recommendation; not chosen)_ — not chosen. Full grid stays cheap; the one region worth resolving finely (near the degenerate case) gets it, without multiplying the whole sweep's cost.

## Consequences

The natural complement to VOI being zero at beta=1 and increasing in beta -- worth resolving the actual shape, not just the endpoints.

**What this gates:** Total compute budget for the M3 sweep, alongside
[VOI-02](VOI-02%20Misspecification%20and%20honesty%20arms.md)'s honesty-arm multiplier — worth sizing
both together before committing to a resolution, since they compound.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The coarse grid in A/C shows a curve shape that looks like it might be non-monotonic or has a kink
compute didn't anticipate — that's the signal to add resolution generally, not just near β=1.

**Depends on:** `X-06`, `MOD-04`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
