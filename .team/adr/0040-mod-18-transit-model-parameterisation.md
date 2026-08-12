# 0040. MOD-18: Transit model parameterisation
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-18
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1 — the simulator cannot generate arrival ages without this.*

**Why this card exists.**

[MOD-11](MOD-11%20Arrival%20age%20distribution.md)=C chose to derive arrival age from an **explicit transit temperature model** rather than
assert a prior on it directly. That is the more ambitious choice and the right one for the argument —
it is what turns *transit dominates effective age* from an assumption into a derived claim. But it
means the transit model now needs inputs, and [X-08](X-08%20Data%20provenance.md)=B made those inputs load-bearing rather than
decorative.

**What the model needs.**

Arrival age is the Arrhenius-weighted integral of the temperature history a lot lived through before
it reached the shelf. So at minimum: a **transit duration** distribution, a **temperature** process
over that duration, and an **activation energy** setting how strongly temperature accelerates the
clock.

**The claim that rests on these numbers.**

If transit dominates effective age for a 7-day item, then the highest-ROI date field is on the
**receiving dock, not the register** — the free ASN field beats the hardware ([SCN-F2a](SCN-F2a%20Pack%20date%20on%20the%20supplier%20ASN.md)). That is
the most contrarian thing the project can say, and it is entirely a consequence of the numbers chosen
here. They need to be defensible.

**The Jensen point, which is easy to lose.**

Because the acceleration factor is **convex** in temperature, **variance costs shelf life at fixed
mean**. A lot that averaged the right temperature but swung around it arrives older than one that
held steady. So the temperature *spread* is not a nuisance parameter — it is part of the mechanism,
and a model that only carries a mean will understate arrival age systematically.

## Decision

We will adopt **A — Duration and temperature distributions from published cold-chain studies**.

**A — Duration and temperature distributions from published cold-chain studies.** Chosen on the board.

## Alternatives considered

- **B — A single effective transit-stress parameter, swept** — not chosen. Collapse the whole transit leg into a single stress scalar and sweep it. Cheap, fully controllable, and it makes the arrival-spread diagnostic ([FIL-11](FIL-11%20How%20we%20know%20the%20filter%20works.md)) trivial to run — but it forfeits the right to quote the dominance claim as a finding.
- **C — Full multi-leg cold chain** — not chosen. harvest, pre-cool, line haul, DC dwell, store delivery

## Consequences

**Depends on:** `MOD-11`, `X-08`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
