# 0061. CTL-04: Rollout horizon and terminal value
STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: CTL-04
GROUP: CTL
PROVENANCE: notes-agree
TIER: 2
MILESTONE: M2 — controller and multi-scenario

## Context

*Milestone: M2. Only relevant if [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md) chose B or C.*

**The question.**

$J_\pi$ is a forever-quantity; a simulated rollout path is not. Truncating at some horizon $H$ is
forced, and unlike sampling noise (which CRN fixes,
[CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md)) truncation bias is systematic: stock still on
the shelf at day $H$ contributed nothing to recorded profit but was already paid for, so every
candidate is penalised for inventory that in reality sells on day $H+1$. The push is the same
direction on every path — under-ordering, hence avoidable stockouts.

**The salvage has a direction of error both ways.**

Too low: keeps the under-ordering bias B exists to remove. Too high: the rollout hoards, collecting
credit at the horizon for stock it never has to justify selling. Margin (not retail price) in $V_T$
keeps it roughly honest. Guardrail: if $V_T$ turns out to be a large fraction of total path profit,
$H$ is too short.

## Decision

We will adopt **B — Fixed H ≈ 2× shelf life, plus survival-weighted terminal salvage**.

**B — Fixed H ≈ 2× shelf life, plus survival-weighted terminal salvage.** V_T = m * sum_l w_long(tau_l) n_l, w_long computed from queue position under oldest-first allocation.

## Alternatives considered

- **A — Fixed H, zero terminal value** — not chosen. Simplest; systematically under-orders because every leftover unit at H is charged as a total loss.
- **C — Infinite-horizon / discounted formulation** — not chosen. No truncation bias by construction, but no simulator naturally terminates and the machinery is heavier for no evident gain here.

## Consequences

V_T = m * sum_l w_long(tau_l) n_l, w_long computed from queue position under oldest-first allocation.

**What this gates:** The $H$-plateau sweep becomes an appendix figure regardless of which option is chosen (B needs it as
validation, A and C would need it to demonstrate their own behaviour). Sets $H$ and $M$ for the
compute-cost accounting referenced in [CTL-02](CTL-02%20Depth%20of%20policy%20improvement.md).

**Revisit if:** The $H$-plateau sweep doesn't flatten — that's the built-in signal that B's parameters need
adjustment (or that C is worth the extra engineering after all).

**Depends on:** `CTL-02`, `MOD-07`, `X-11`

**Milestone:** M2 — controller and multi-scenario
