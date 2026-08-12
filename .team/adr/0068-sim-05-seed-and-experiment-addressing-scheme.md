# 0068. SIM-05: Seed and experiment addressing scheme
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SIM-05
GROUP: SIM
PROVENANCE: yours
TIER: 3
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

*Milestone: M3, but the design decision is worth settling early since it shapes how simulation code is
written from the start, not bolted on after.*

**The question.**

Your own project notes are explicit about this, in a section CLAUDE.md quotes directly:

> "Seeding is not cosmetic here: the rollout in the controller depends on common random numbers, which
> requires addressing random draws by **semantic slot** (`U[path, day, :demand]`) rather than by draw
> order. Consuming a flat stream sequentially desynchronises the moment one candidate draws a different
> number of variates, with no error and no symptom — just quietly worse decisions."

[SIM-02](SIM-02%20Outer-loop%20CRN%20scope.md) extends that requirement from the rollout's inner
candidate loop to the entire VOI sweep, which makes this a project-wide infrastructure choice, not a
local implementation detail of the controller.

## Decision

We will adopt **A — Hierarchical seeded RNG per semantic slot -- e.g. a SeedSequence spawn tree keyed by (arm, replication, day, stream name)**.

**A — Hierarchical seeded RNG per semantic slot -- e.g. a SeedSequence spawn tree keyed by (arm, replication, day, stream name).** Addresses randomness by slot, not by draw order, per CLAUDE.md section 6 -- the recommended approach.

## Alternatives considered

- **B — Single global RNG consumed sequentially, addressed by call order** — not chosen. CLAUDE.md explicitly warns this desyncs silently the moment two arms draw a different number of variates.
- **C — Pre-generate and store every draw as arrays indexed by semantic slot, load rather than generate on the fly** — not chosen. Most reproducible and debuggable; highest memory and storage cost across a full sweep.

## Consequences

Addresses randomness by slot, not by draw order, per CLAUDE.md section 6 -- the recommended approach.

**What this gates:** This is the concrete infrastructure [SIM-02](SIM-02%20Outer-loop%20CRN%20scope.md)'s "full CRN" option
requires to exist. Also the mechanism [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)'s rollout
already needs regardless of what this card decides for the outer loop — so the only real question here
is scope (rollout-local vs project-wide), not whether to build it at all.

**Revisit if:** A specific stream's reproducibility needs to be audited by hand often enough that generating on demand
becomes a workflow friction — at that point, layer C's on-disk cache on top of A for just that stream,
rather than switching wholesale.

**Depends on:** `SIM-02`, `X-10`

**Milestone:** M3 — VOI sweep, oracles, misspecification arms
