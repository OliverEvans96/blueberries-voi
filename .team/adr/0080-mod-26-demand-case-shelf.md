# 0080. MOD-26: Demand μ=30, V/M=2, case size 8, plus case-size sensitivity at 4

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-26
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

MOD-09=A fixes the demand **family** (negative binomial, i.i.d., known to every policy) but not
mean or dispersion, and no card fixed **case size**. Together those set shelf dwell — how much of
the hazard curve the product traverses in store — and therefore whether anything spoils.

Case size is especially load-bearing under CTL-01's `caseRound(...)`: if the informed vs uninformed
gap in effective inventory is reliably smaller than one case, VOI is zero **by rounding**. X-12=A
turned off the tripwire, so nothing else catches a rounding artefact unless we measure it (Gate 0b)
and keep a cheap sensitivity cell.

## Decision

We will adopt **B — Defaults plus case-size sensitivity**:

| Parameter | Default | Note |
| --- | --- | --- |
| Demand mean μ | 30 punnets/store/day | Fast-turning berry SKU |
| NB dispersion | V/M = 2 ⇒ NB `r = 30` | Overdispersion typical of fresh |
| Case size | 8 punnets | Plus **one sensitivity cell at case size 4** |
| Shelf capacity | Unconstrained | X-04=A is order-quantity only |

M1 open-loop driver (not the M2 controller): age-blind base-stock **S = 60**
(`S = μ · (1 + LT)` with LT = 1), ordering `max(0, S − on_hand)` after delivery accounting. Daily
delivery per X-11.

## Alternatives considered

- **A — Defaults table only, no case-size sensitivity** — rejected because X-12's own body names
  case size as the thing that can swallow the entire result; one extra cell is the cheapest
  insurance.
- **C — Calibrate demand to a published fresh-berry store-day distribution first** — rejected for
  M1: more work, and X-08 already licenses synthetic instances; can revisit later without blocking
  the filter.

## Consequences

- All M1 sim / Gate 0b / FIL-11 runs default to μ=30, r=30, case=8 unless the sensitivity cell is
  explicitly selected.
- Gate 0b and any caseRound swallow narrative must report both case sizes when the gap is near one
  case.
- Defaults are **veto defaults**, not FreshNet-calibrated truth; dwell vs η_ref jointly decide
  whether the headline number can exist.
- Cost: one extra evaluation cell; no capacity constraint in M1.

**Depends on:** `MOD-09`, `X-12`, `X-07`, `X-11`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
