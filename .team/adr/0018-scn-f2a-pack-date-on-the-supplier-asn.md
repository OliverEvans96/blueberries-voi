# 0018. SCN-F2a: Pack date on the supplier ASN
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-F2a
GROUP: SCN
PROVENANCE: contested
TIER: 2

## Context

**What the store observes.**

A **pack or harvest date field on the supplier's advance ship notice**. No hardware, no 2D barcode,
no checkout integration — a data field in an EDI document that many suppliers could populate today.

Formally it is not a new observation *structure* at all: it narrows the prior on arrival age. That
makes it by far the cheapest card here to implement — one parameter change, no new filter, no new
likelihood.

**Why it carries the most surprising claim in the project.**

For a 7-day item, **transit dominates effective age**. If that holds, the highest-ROI date field is
on the **receiving dock, not at the register** — the free thing beats the hardware.

That is the finding most likely to interest someone who actually works in grocery, and it is
contrarian in exactly the way a hiring artefact benefits from. It is also falsifiable by this
project's own machinery.

**Why in or out.**

**In:** near-zero marginal cost, highest claim-per-unit-of-work ratio on the board.

**Out:** it is the rung most exposed to the arrival-staggering problem — if the arrival-age prior is
already tight, narrowing it further buys nothing and the result is a flat line.

> **Recommended: In.** The dropped cadence/staggering axis (see [X-06](X-06%20VOI%20sweep%20axes.md)) makes the flat-line risk
> higher than it was, which is worth knowing before committing.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.

**Depends on:** `X-06`
