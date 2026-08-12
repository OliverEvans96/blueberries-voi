# 0074. ENG-02: Repo and module layout
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: ENG-02
GROUP: ENG
PROVENANCE: newly-raised
TIER: 3

## Context

**The question.**

[X-09](X-09%20Language%20and%20stack.md) settled the language (Python, JS for the browser sim) and
[X-10](X-10%20Reproducibility%20standard.md) settled the reproducibility standard (one repo, scripted
end to end, seeded, figures committed). Neither settles how the code is organised inside that repo —
and this project has one specific, load-bearing constraint that the layout has to protect:

> **The simulator and the filter must share the transition code**, so misspecification is switched on
> deliberately rather than acquired by accident.

A layout that makes it easy to duplicate the daily-recursion logic between "the simulator" and "the
filter's transition model" defeats that guarantee silently — two copies drift, nobody notices, and
every downstream VOI number is contaminated by an unintended difference no test catches.

## Decision

We will adopt **A — Single Python package, one module per subsystem (sim/, filter/, controller/, voi/, viz/)**.

**A — Single Python package, one module per subsystem (sim/, filter/, controller/, voi/, viz/).** Shared transition code lives in one place and is imported by both sim and filter, per CLAUDE.md section 4.

## Alternatives considered

- **B — Notebook-first — each experiment is a notebook, shared code factored out opportunistically** — not chosen. Fast to iterate, easy to lose the "sim and filter share transition code" guarantee.
- **C — Script-per-experiment, no shared package** — not chosen. Simplest to start; duplicates the transition logic across sim and filter, which is exactly the bug CLAUDE.md flags as silent and dangerous.

## Consequences

Shared transition code lives in one place and is imported by both sim and filter, per CLAUDE.md section 4.

**What this gates:** Where the [MOD-12](MOD-12%20Within-day%20order%20of%20operations.md) transition function physically
lives, and therefore how the "shared code" assertion test is written.

**Revisit if:** Never, in practice — this is closer to a convention than a modelling choice. Flagged mainly because
CLAUDE.md's own instructions treat the transition-code-sharing rule as important enough to call out
by name, so the layout that protects it deserves an explicit yes rather than an implicit default.

**Depends on:** `X-09`, `X-10`
