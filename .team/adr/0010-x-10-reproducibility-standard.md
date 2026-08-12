# 0010. X-10: Reproducibility standard
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-10
GROUP: X
PROVENANCE: newly-raised
TIER: 3

## Context

**The question.**

Low stakes conceptually, but this is a hiring artefact and the standard is part of the artefact.
Deciding now costs nothing; deciding late means retrofitting.

## Decision

We will adopt **A — One repo, scripted end to end, seeded, figures committed**.

**A — One repo, scripted end to end, seeded, figures committed.** Make all regenerates every figure in the post from scratch.

## Alternatives considered

- **B — Notebook-driven** — not chosen. One notebook per section; narrative and code interleaved.
- **C — Scripted plus pinned manifest plus CI** — not chosen. As A, with a lockfile and a GitHub Action that rebuilds figures.

## Consequences

make all regenerates every figure in the post from scratch.

**What this gates:** Nothing downstream; it is a working convention. Listed because it is cheap now and annoying later.

**Revisit if:** Sweeps grow past what a laptop will run overnight, at which point the manifest and job scripting
matter more.

**Depends on:** `X-09`
