# 0047. FIL-02: What is sampled versus marginalised
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-02
GROUP: FIL
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2 — only bites if [FIL-01](FIL-01%20Filter%20family.md) takes the Rao-Blackwellised route.*

**The question.**

Rao–Blackwellisation is only a win if you marginalise the *right* coordinate. The rule is: marginalise
the one you can handle in closed form, and preferably the one that is hardest to explore.

**Why age is the coordinate to marginalise.**

The spoilage likelihood is Binomial in the cohort's age, so on a discrete age grid the update is a
**vector multiply** — closed form, no sampling, no degeneracy along age ever. And age is precisely the
coordinate with no process noise, i.e. the one a sampler explores worst.

Cost is roughly (particles × cohorts × grid points) per day-step — on the order of a few million
operations, which is nothing.

**Why not C.**

Counts are integer-valued, hard-constrained (non-increasing between deliveries, tied to observed
flows, and a stockout is an exact observation of zero) and coupled across cohorts by the allocation
normaliser. There is no closed form to exploit.

**The thing this makes cheap that is easy to miss.**

Because arrival age is static with no process noise, propagating the belief **inside a rollout path**
is also just a vector multiply per day. So the same structure that makes the filter cheap makes
belief-space rollout cheap — no nested particle filter. That is a large saving in the controller, and
it is a consequence of a decision made here.

> **Recommended: A.**

## Decision

We will adopt **A — Sample counts, marginalise arrival age on a grid**.

**A — Sample counts, marginalise arrival age on a grid.** Chosen on the board.

## Alternatives considered

- **B — Sample everything** — not chosen on the board.
- **C — Sample arrival age, marginalise counts** — not chosen on the board.

## Consequences

**Depends on:** `FIL-01`

**Milestone:** M2 — controller and multi-scenario
