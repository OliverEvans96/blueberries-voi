# 0006. X-06: VOI sweep axes
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-06
GROUP: X
PROVENANCE: contested
TIER: 1
AGAINST-RECOMMENDATION: true

## Context

**The question.**

The VOI surface is the headline figure, so its axes are the claim. Your bullets say
(knowledge scenario x beta). The notes add two more axes almost in passing, and one of them is a
go/no-go on the technical core.

**Why cadence matters.**

The controller note fixes daily delivery, then admits daily delivery is *the regime where age
information matters least* — stock turns fast and never gets old. Real berry cadence is 3–5x/week. At
3x/week the Friday order faces a protection interval of 4 rather than 2, taking effective inventory
in the worked example from 60 units to 49 and roughly doubling the gap against the age-blind policy.
So the base case is a floor, and the headline understates by construction.

**Why arrival staggering matters more.**

In-store ageing is assumed constant and known, so it adds the same amount to every lot's age and
therefore **cannot help you tell lots apart**. All identification of relative freshness comes from
lots arriving at *different* ages. If cadence is rigid and the arrival-age prior is tight, lots become
nearly exchangeable, the composition posterior collapses to the prior, and the filter is decoration —
the entire D0 to D4 VOI would then be a statement about where you got your prior.

That is a two-hour experiment and it should be an axis, not a footnote. It is also a result worth
being willing to publish.

## Decision

We will adopt **A — scenario x beta**. Chosen against the card recommendation of **C — scenario x beta x cadence x arrival staggering**.

**A — scenario x beta.** ⚑ Against the card's recommendation (C). Your bullets, literally. Two axes, small grid, fast.

## Alternatives considered

- **B — scenario x beta x delivery cadence** — not chosen. Cadence sets the protection interval, which is where age information bites.
- **C — scenario x beta x cadence x arrival staggering** _(card recommendation; not chosen)_ — not chosen. Adds the axis that determines whether the filter does anything at all.

## Consequences

Your bullets, literally. Two axes, small grid, fast.

**What this gates:** SIM harness parameterisation · VOI compute budget · whether the daily-delivery base case survives.

Deliberate override of the card recommendation (⚑). Do not reopen without asking Oliver.

**Revisit if:** The staggering axis turns out to be flat — then it collapses to a single validating figure and B is
the surface.

**Depends on:** `X-01`, `X-05`
