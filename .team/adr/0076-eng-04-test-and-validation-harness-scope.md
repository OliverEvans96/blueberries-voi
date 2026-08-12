# 0076. ENG-04: Test and validation harness scope
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-04
GROUP: ENG
PROVENANCE: newly-raised
TIER: 2
AGAINST-RECOMMENDATION: true

## Context

**The question.**

Several already-settled decisions each carry a specific, named correctness gate that has to be
*checked*, not just built:

| Gate | From | What it catches |
| --- | --- | --- |
| Shared transition code between sim and filter | CLAUDE.md §4, [ENG-02](ENG-02%20Repo%20and%20module%20layout.md) | Sim/filter misspecification drifting in silently |
| Conditional survival ratio, never hazard×Δt | [MOD-04](MOD-04%20Spoilage%20law.md) | An error that grows with β — the project's own sweep axis |
| β=1 degeneracy check | [CTL-05](CTL-05%20Baseline%20ladder.md) / [CTL-06](CTL-06%20Optimality%20certificate.md) | Age-aware and age-blind policies must coincide when w is constant |
| CRN stream desync | [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) | "The silent bug" — no error, no symptom, just worse decisions |
| FIL-11's staged calibration gate | [FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md) | Whether the filter recovers truth at all |

None of these fail loudly on their own — that's precisely why the notes call them out. The question
is how much of catching them is automated versus left to disciplined manual practice.

## Decision

We will adopt **A — Automated test suite — every gate below runs in CI, fails the build if broken**. Chosen against the card recommendation of **B — Scripted but manual — each gate is a runnable script/notebook, run and inspected by hand at milestones**.

**A — Automated test suite — every gate below runs in CI, fails the build if broken.** ⚑ Against the card's recommendation (B). Highest confidence, most upfront engineering.

## Alternatives considered

- **B — Scripted but manual — each gate is a runnable script/notebook, run and inspected by hand at milestones** _(card recommendation; not chosen)_ — not chosen. Matches the bottom-up, milestone-gated way you've chosen to build (M1 -> M2 -> M3).
- **C — Ad hoc — checks exist where convenient, no enforced discipline** — not chosen. Fastest short-term, and the one CLAUDE.md's own trap list warns against by naming specific silent-failure modes.

## Consequences

Highest confidence, most upfront engineering.

**What this gates:** Whichever gates end up in the harness should run at the milestone boundaries already defined in
[PROTOCOL.md](../PROTOCOL.md) §8b — end of M1 (shared transition code, survival-ratio, FIL-11 stages),
end of M2 (β=1 degeneracy, CRN desync, DP certificate), before M3's sweep (all of the above, since a
full VOI sweep amplifies any bug that survived to that point).

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** B's manual discipline slips in practice — e.g. a gate gets skipped and a bug from CLAUDE.md's trap
list actually reaches a VOI number. That's the concrete trigger for promoting to A.

**Depends on:** `X-10`, `FIL-11`, `CTL-06`
