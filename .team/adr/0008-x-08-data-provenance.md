# 0008. X-08: Data provenance
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-08
GROUP: X
PROVENANCE: newly-raised
TIER: 2

## Context

**The question.**

Your bullets say "so: synthetic" for the inference idea, and the whole design assumes a simulator
that knows ground truth. But there is a spectrum between "made-up numbers" and "real data", and
where you sit on it determines how much the headline number can be claimed to mean.

## Decision

We will adopt **B — Synthetic, with priors calibrated from published shelf-life studies**.

**B — Synthetic, with priors calibrated from published shelf-life studies.** Weibull and Arrhenius parameters anchored to real berry literature.

## Alternatives considered

- **A — Fully synthetic, arbitrary parameters** — not chosen. Self-contained, no sourcing risk, no external validity.
- **C — Attempt real retail sales/waste data** — not chosen. Public grocery datasets, or the strawberry cold-chain logger data.

## Consequences

Weibull and Arrhenius parameters anchored to real berry literature.

**What this gates:** Whether the VOI number is quotable in dollars · calibration appendix · MOD parameter priors.

**Revisit if:** The literature turns out not to report Weibull shape for berries at all, in which case beta's prior
is your own and B collapses toward A for the one parameter that matters most.

**Depends on:** `X-01`
