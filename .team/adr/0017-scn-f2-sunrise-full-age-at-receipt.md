# 0017. SCN-F2: Sunrise full — age at receipt
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: SCN-F2
GROUP: SCN
PROVENANCE: notes-agree
TIER: 2

## Context

**What the store observes.**

- Complete age-resolved sales
- **Age at receipt observed** — via case-level 2D, or via the ASN pack-date field
- Age census on demand: scan the case, get the shelf's age histogram
- Optionally **cold-chain exposure per lot** from EPCIS sensor data, so the hazard becomes
  conditional on thermal history rather than a fixed curve

**Why this rung matters structurally.**

At full telemetry, effective age is *measured*, so the age coordinate collapses out of the state
entirely and what remains is a **pure count HMM**. Not "reduces to" — *is*. That gives the post a
clean line:

> The model is exactly a small hidden Markov model at exactly the data level Sunrise 2027 delivers.
> Below it you need Monte Carlo; at it and above, the forward algorithm runs in microseconds.

**Why in or out.**

**In:** it is the top of the ladder and the thing being priced.

**Out:** the cold-chain telemetry half is speculative post-2029 infrastructure. A version without
telemetry (age at receipt only) is most of the value for much less speculation.

> **Recommended: In.** Consider splitting telemetry off as its own rung if it turns out to be the
> only place the Weibull shape parameter becomes identifiable.

## Decision

We will adopt **A — In**.

**A — In.** Chosen on the board.

## Alternatives considered

- **B — Out** — not chosen on the board.

## Consequences

**Revisit if:** Membership of the knowledge ladder changes.
