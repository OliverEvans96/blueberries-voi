# 0079. MOD-25: Fixed base σ=0.5 plus one uniform-picking sensitivity cell

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: MOD-25
GROUP: MOD
PROVENANCE: newly-raised
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

MOD-07=A fixes the picking-kernel **form** `w ∝ S(τ)^(1/σ)` but no settled card fixed **σ**. Under
X-06=A the VOI surface is only (scenario × β), so σ is a single fixed number — and it is
high-leverage:

1. **It drives L.** Fresh-biased σ makes old cohorts linger and die (MOD-13); L is the exponent in
   FIL-13's tractability arithmetic.
2. **It confounds identifiability.** Fresh-biased picking and rising hazard both remove old units;
   fixing σ silently fixes how hard inference is.
3. **It is the post's contrarian assumption.** In self-service produce, issuing order is not a
   control; σ is the number that claim rests on.

## Decision

We will adopt **B — Fixed base case σ = 0.5** (moderately fresh-biased) **plus one sensitivity cell
at uniform / random picking** (the MOD-07 degenerate switch, σ → ∞ / flat weights).

Report the stationary live-cohort distribution L under both cells whenever FIL-13 arithmetic or
figures depend on L.

## Alternatives considered

- **A — One fixed moderately fresh-biased σ with no sensitivity** — rejected because the whole
  result would sit on an unjustified scalar with no bound on the L / identifiability artefact.
- **C — Add σ as a third VOI sweep axis** — rejected because it reopens X-06=A, which deliberately
  fixed the surface at two axes.

## Consequences

- Base M1 runs use σ = 0.5; harness must expose a uniform-picking switch for one extra evaluation.
- FIL-13 bakeoff and L diagnostics must quote which σ cell produced the L distribution.
- Interim M1 physics defaults used with this choice: β = 2.0, η_ref = 14 d @ T_ref = 0 °C,
  Q10 = 3.0, T_store = 4 °C (veto defaults for M1 driver / filter validation; not a third sweep).
- Cost: one extra evaluation cell per relevant experiment; does not expand the VOI surface.

**Depends on:** `MOD-07`, `MOD-13`, `X-06`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
