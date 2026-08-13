# Intake 2026-08-12 — Plan and implement M3

## Request (their words)

> Please plan and implement M3 in a new branch. Proceed autonomously and ask me for clarifications at the end.

## What they want

A complete M3 milestone: the value-of-information sweep over knowledge scenarios and spoilage shape
β, planned under `.team/`, implemented with TDD on a new branch from the current integration tip,
verified locally, with clarifying questions deferred to the end rather than blocking progress.

## In scope

- Discover M3 from board ADRs / plans (VOI-01–04, SIM outer loop)
- Plan (ADRs/specs/plan file), implement `voi/` library + smoke gates, changelog / qa / reviews
- Branch from M2 verify tip; do not merge to `main`

## Out of scope

- Honesty / misspecification arms (VOI-02=A ⚑)
- ENG-01 / Pyodide browser packaging
- Cadence or arrival-staggering VOI axes (X-06=A ⚑)
- Merging M2 or M3 onto `main`

## Open questions

- [ ] Confirm production β grid upper bound and exact 10+ knot placement beyond “includes 1.0”
- [ ] Confirm default `ProfitCosts` for headline VOI vs M2 multi-scenario defaults
- [ ] Whether F1/F1s closed-loop must fully score lot-resolved masks in M3v1 or may smoke-wire

## Assumptions if unanswered

- Production β grid = 10 values from 1.0 to 4.0 inclusive (linspace); CI smoke uses `{1.0, 2.0}`
- Reuse M2 multi-scenario `ProfitCosts(unit_margin=2.0, waste_cost=1.5, stockout_penalty=3.0)`
- Wire all ADR 0096 columns through CRN cell; lot-resolved masks use existing `mask_for` + RBPF
