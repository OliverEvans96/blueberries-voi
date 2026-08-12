# 0045. MOD-23: Strawberry-logger to blueberry substitution
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-23
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1. Product substitution under [X-07](X-07%20Scope%20of%20the%20instance.md)=blueberry and [MOD-18](MOD-18%20Transit%20model%20parameterisation.md)=A.*

**The question.**

[X-07](X-07%20Scope%20of%20the%20instance.md)=A is blueberries. The only open multi-shipment,
multi-position, harvest-started berry pallet temperature dataset named in the notes is **Abdella,
Brecht & Uysal 2021** — strawberries. Do we accept that substitution for the arrival-age generator,
or insist on a blueberry-specific chain model?

## Decision

We will adopt **A — Accept Abdella strawberry traces for the blueberry arrival-age generator**.

**A — Accept Abdella strawberry traces for the blueberry arrival-age generator.** Kinetics (η, Q₁₀)
stay blueberry (UC Davis); only the thermal-path ensemble is borrowed. One-sentence appendix caveat
on species. Keeps the empirical multi-position harvest-started bootstrap that
[MOD-21](MOD-21%20Abdella%20transit%20sampling%20frame.md) and [MOD-06](MOD-06%20Clock%20origin%20and%20left-truncation.md)
need; Ktenioudaki-style virtual chains remain a secondary cross-check, not the primary prior.

## Alternatives considered

- **B — Require a blueberry virtual-chain instead** — not chosen. Ktenioudaki-style hour×°C scenarios; blueberry-specific, not a logger bootstrap.

## Consequences

One-sentence appendix caveat. Best open multi-position harvest-started berry pallet dataset.

**What this gates:** Whether [MOD-21](MOD-21%20Abdella%20transit%20sampling%20frame.md) is live · credibility of the
calibrated arrival-age generator · appendix wording.

**Revisit if:** An open blueberry pallet-logger dataset of comparable resolution appears, or FIL-11 fails under the
Abdella mix for reasons that look like species-specific chain structure rather than arrival spread.

**Depends on:** `X-07`, `X-08`, `MOD-18`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
