# 0086. RichObs + UNOBSERVED + scenario masks (FIL-08=C)

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-08 (M1.5 elaboration)
MILESTONE: M1.5 — filter complete across data-availability rungs

## Context

FIL-08=C already locks “one filter with the richest observation model; other rungs by masking.”
M1 shipped only `P1Obs(sales_total, waste_total, arrivals)`, so every rung was forced into the same
three integers. Missing fields were never expressible: writing `0` for “no waste observed” on P0
would falsely update as “zero waste.” M1.5 must compare settled data-availability rungs
(P0, P1, F1, F1s, F2a, F2) fairly under one RBPF binary, without inventing receiving error
(MOD-17=A) or reopening ⚑ cards.

## Decision

We will use a single frozen **`RichObs`** schema as the filter’s observation type. Fields absent
under a rung are set to a sentinel **`UNOBSERVED`**, never to numeric zero or an empty map that
the likelihood would treat as data. An **`ObsMask`** (or `ScenarioId → frozenset` of present field
names) with `mask.apply(rich) -> RichObs` materialises that rule. One `RBPF` class takes masked
`RichObs`; scenario is a mask argument, not a subclass. SCN-B-state is a verification bypass (true
state → belief identity), not a mask that invents observations.

Present-field table for M1.5 filter masks:

| Field | P0 | P1 | F1 | F1s | F2a | F2 |
| --- | --- | --- | --- | --- | --- | --- |
| `arrivals` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sales_total` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `waste_total` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `sales_by_lot` | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| `waste_by_lot` | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| `pack_date` / ASN age hint | ✗ | ✗ | ✗ | ✗ | ✓ | (subsumed) |
| `age_at_receipt` | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| `lot_ids_live` | weak | weak | ✓ | ✓ | weak | ✓ |

P0 vs P1 differs only by presence of `waste_total` (MOD-17). F1 defaults to ρ=1 unbiased
lot-resolved sales in M1.5; biased-ρ is sensitivity-only, not a DoD gate.

## Alternatives considered

- **Keep `P1Obs` and branch likelihoods per rung** — rejected because it contradicts FIL-08=C and
  invites divergent filter implementations that contaminate rung comparisons.
- **Encode missing as `0` / empty dict with a parallel boolean mask** — rejected because callers
  routinely forget the boolean and the likelihood silently conditions on false zeros (the P0 bug).
- **Separate observation dataclass per rung** — rejected because it forks types at the RBPF
  boundary and makes shared CRN multi-rung Stage A harder than one schema + mask.

## Consequences

- Easy: fair multi-rung Stage A/B under shared CRN; tests can assert “masked field never enters LL.”
- Hard: every consumer of observations (sim→filter adapters, viz harnesses) must understand
  `UNOBSERVED`; `P1Obs` becomes a compatibility shim or is retired behind a RichObs constructor.
- Locked: missing ≠ zero for M1.5 and later VOI columns that reuse this schema.
- Revisit only if Oliver reopens FIL-08 or adds a new IN rung with a field not in `RichObs`.

**Depends on:** FIL-08, MOD-14, MOD-15, MOD-17, SCN-P0/P1/F1/F1s/F2a/F2, SCN-B-state
**Does not reopen:** FIL-01, FIL-08, SCN-P2/F3/B-clair
