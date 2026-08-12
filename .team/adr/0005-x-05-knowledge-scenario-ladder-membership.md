# 0005. X-05: Knowledge scenario ladder — membership
STATUS: SUPERSEDED BY SCN-* (ladder membership moved to per-rung cards)
DATE: 2026-08-12
BOARD-ID: X-05
GROUP: X
PROVENANCE: contested
TIER: 1

## Context

**Superseded — membership is decided scenario by scenario in the SCN group.**

Rather than picking a pre-bundled ladder, each rung is now its own in/out card. This card survives as
the index and as the record of the two structural points that apply across all of them.

**The naming.**

The authoritative definitions live in
[Data Availability Scenarios and the Value of Age Information](../../Data%20Availability%20Scenarios%20and%20the%20Value%20of%20Age%20Information.md) §2 and use **P0/P1/P2/F1/F2/F3**
(present-day / future), not the D0–D5 naming that appears in the later outline. The SCN cards use the
P/F names. Where a later note says "D3", it means F1; "D5" means F2 with cold-chain telemetry.

**The split worth keeping whatever else is cut.**

The plan's separation of lot scanning into **sales-side** and **shrink-side** is an improvement on the
original ladder, because the two identify different objects:

> Lot ID at the till identifies the **picking** kernel. Lot ID on the shrink gun identifies the
> **spoilage** kernel. Sunrise 2027 delivers both, but they are different purchases with different
> business cases.

That is also the clean break for the φ/μ confounding that stopped the A=7 recovery — it breaks it by
*measurement design* rather than by prior. Hence SCN-F1 and SCN-F1s are separate cards.

**Every rung costs the same three things.**

Worth holding in mind while marking cards in or out. Each additional rung is:

1. an observation model and likelihood,
2. a filter implementation (they are not all the same algorithm — some are exactly solvable and some
   need Monte Carlo), and
3. a column of the VOI surface, which means a full policy evaluation sweep.

Rungs that differ only in a **prior width** (SCN-F2a is the clearest case) cost far less than rungs
that change the observation *structure*.

**The cards.**

| Card | Rung | One line |
| --- | --- | --- |
| SCN-P0 | Books only | Receipts, censored POS, drifting book inventory, shrink as a periodic accrual |
| SCN-P1 | Shrink gun | Daily item-level waste, under-reported at compliance κ |
| SCN-P2 | Instrumented store | Date audits, markdown scans, variable-weight categories already age-resolved |
| SCN-F1 | Sunrise partial, POS | Age-resolved sales for a biased fraction ρ of units |
| SCN-F1s | Shrink-gun lot ID | Age-resolved *deaths* — identifies the spoilage kernel directly |
| SCN-F2a | Pack date on the ASN | Available today, no hardware; narrows the arrival-age prior only |
| SCN-F2 | Sunrise full | Age at receipt observed; optionally cold-chain exposure per lot |
| SCN-F3 | Sunrise plus ESL | Price at age becomes a decision — changes the action space |
| SCN-B-state | Perfect state oracle | Ceiling on what information about inventory can buy |
| SCN-B-clair | Perfect foresight oracle | Ceiling on everything; the denominator |

## Decision

Superseded 2026-08-12 at Oliver's request — membership decided per rung.

## Alternatives considered

- Membership is decided on individual `SCN-*` cards instead of this aggregate card.

## Consequences

**Revisit if:** Two adjacent rungs produce indistinguishable VOI, in which case merge them and say so in the post.

**Depends on:** `X-01`
