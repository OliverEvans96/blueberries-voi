# 0096. M3 knowledge-scenario columns for the VOI sweep

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: X-05 / X-06 (M3 column set)
GROUP: VOI
PROVENANCE: M3 Wave 0 lock
TIER: 1
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

X-06 locks axes to **scenario × β** but not the exact scenario column list for the shipped sweep.
M1.5 settled filter masks **P0, P1, F1, F1s, F2a, F2** plus **B-state** as an oracle ceiling (not a
mask). M2 evaluated P1 / B-state / Rung 0 for the controller ladder, not dollar VOI. VOI-01 anchors
percentage improvement to the **least-informed rung (P0)**. Including Rung 0 or constant-order as
VOI columns would confuse information VOI with policy-family VOI already reported by CTL-05.

## Decision

We will:

1. Define the M3 VOI **information columns** as:
   - **Denominator / baseline:** **P0** (books only)
   - **Filter rungs:** **P1, F1, F1s, F2a, F2** (M1.5 `mask_for` scenarios)
   - **Ceiling:** **B-state** (oracle `ShelfBelief`; not `mask_for`)
2. Evaluate the **same age-aware policy family** (damped SW + one-step rollout) under each column’s
   belief; do **not** add Rung 0 / constant-order as VOI sweep columns.
3. Report VOI-01 metrics for every non-P0 column as deltas vs P0 under the shared CRN cell
   (SIM-02), at each β.
4. Keep SCN-B-clair, SCN-P2, SCN-F3, and honesty arms **out** (⚑ / parked).

## Alternatives considered

- **Only P1 vs B-state (M2 multi-scenario set)** — rejected: M3’s purpose is the information ladder
  across settled data-availability rungs, not a controller smoke.
- **Include Rung 0 / constant-order as VOI columns** — rejected: those are policy baselines
  (CTL-05), not knowledge scenarios; mixing them muddies the headline claim.
- **Omit B-state** — rejected: the oracle ceiling is the natural upper bound for “how much
  information could be worth”; M1.5 already treated it as verification ceiling.

## Consequences

**Easy:** Clear mapping from M1.5 masks + B-state into VOI columns; P0 matches VOI-01.  
**Hard:** F1/F1s/F2a/F2 closed-loop paths must actually apply masks (not P1-only shortcuts).  
**Locked:** VOI denominator is P0; B-state is ceiling, not a filter mask.  
**Revisit if:** Stage A honesty shows a rung cannot identify age under defaults — still report the
column (honest flat VOI), do not drop it silently.
