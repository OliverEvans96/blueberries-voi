# Arrival-only age + counts-only filter (exact WOR)

**Status:** architect locked (T-067) — implement via T-068 → T-069  
**Date:** 2026-08-13  
**ADRs:** [0105](../adr/0105-arrival-only-age-counts-only-exact-wor.md), [0106](../adr/0106-shelfbelief-arrival-prior-age-exports.md)

## Product lock

- Ages: arrival only + MOD-02 clock; no production `mean_field_update`
- Counts: particle filter; transitions match `day_step` physics
- Weights: default exact sequential WOR; multinomial optional via config
- ShelfBelief ages: arrival-prior exports (same wire shape)
- Rationale: in-store age learning dropped (FIL-11 Stage A), not “bootstrap simpler”

## Tickets

| Ticket | Role | Deliverable |
|--------|------|-------------|
| **T-067** | Architect | Intake, ADRs 0105+0106, supersessions, this plan, specs T-068/T-069 |
| **T-068** | qa → implement → review∥verify | Filter core rewrite + guard supersessions |
| **T-069** | qa → implement → review∥verify | Belief export + Stage A docs + changelog |

## Sequencing

T-067 → T-068 → T-069. Do not parallelize T-068 and T-069 writers. Within each
implementation ticket: reviewer ∥ verifier after implement tip.

## Non-goals

CTL-08, MOD-08 sim law change, dropping F2a/F2, claiming Stage A in-store age
contraction fixed, merge to `main`.
