# 0030. MOD-08: Allocation law
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-08
GROUP: MOD
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

Given today's sales total and the picking weights, how are sales split across cohorts?

The exact law is **Wallenius' noncentral multivariate hypergeometric** — sampling without
replacement with unequal weights. Its pmf involves a one-dimensional integral and is genuinely
annoying to evaluate. Multinomial (sampling *with* replacement) is the closed-form approximation, and
it is good until the shelf starts to clear, at which point it is exactly wrong in the regime the
project cares about.

**The argument this settles, and it belongs in the post.**

A bootstrap particle filter **never needs the density — only the ability to simulate it**, which is a
`for` loop over shoppers picking without replacement. That is a real, concrete argument for
sampling-based inference here, and it is more persuasive than the usual "the likelihood is
intractable" hand-wave, because you can show the reader the eight lines of code.

## Decision

We will adopt **A — Simulate shoppers sequentially without replacement**.

**A — Simulate shoppers sequentially without replacement.** Exactly Wallenius; no density ever needed.

## Alternatives considered

- **B — Multinomial approximation** — not chosen. Closed-form pmf, wrong when the shelf nearly clears.
- **C — Multinomial always** — not chosen on the board.

## Consequences

Exactly Wallenius; no density ever needed.

**Depends on:** `MOD-07`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
