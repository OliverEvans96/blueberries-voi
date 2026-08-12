# 0054. FIL-09: Reporting lag on waste
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-09
GROUP: FIL
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

*Milestone: M1.*

**The question.**

In a real store a shrink event on day t may reach the books on day t+2. If the filter treats the
recorded timestamp as the event timestamp, conditional independence breaks and the likelihood is
wrong — quietly, with no error and no obvious symptom.

This is described in the notes as the single most common quiet bug in this class of model. It is on
the board so it is a decision rather than an oversight.

## Decision

We will adopt **A — No lag — waste is booked the day it happens**.

**A — No lag — waste is booked the day it happens.** Chosen on the board.

## Alternatives considered

- **B — Fixed known lag with a buffer in the state** — not chosen. A short buffer in the state. Cheap, and it demonstrates awareness of the operational reality without much cost.
- **C — Stochastic lag** — not chosen. Realistic, and it turns the observation model into a mixture over event days, which is real work for a second-order effect. > **Recommended: A** for M1, and consider B as a one-off robustness arm — "here is what happens if > your shrink data is lagged and you don't model it" is a cheap and practically useful result for > anyone who works with real retail data.

## Consequences

**Depends on:** `FIL-08`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
