# 0088. Stage C redefined as generative check vs day_step

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-11 (M1.5 elaboration of Stage C)
MILESTONE: M1.5 — filter complete across data-availability rungs

## Context

FIL-11=D stages A (contraction) → B (calibration) → C (exact comparison). M1 implemented Stage C as
TV between the particle filter posterior and an “exact” update that used the **same soft likelihood** as the
filter, so TV≈0 did not validate generative agreement with the simulator. After ADR 0087 replaces
soft LL with MC-from-`day_step` scoring, Stage C must be redefined so it **fails** if soft powers
return while the sim stays Wallenius/binomial, and **passes** when filter observation probabilities
match simulator physics within a documented tolerance.

## Decision

We will redefine **FIL-11 Stage C** for M1.5 as a **generative agreement check vs `day_step`**, not
as TV against a soft-LL exact path.

**Pass language:** observation probabilities the filter uses match the simulator’s physics within
tolerance X (TV/KL on discrete masked observations, and/or paired CRN match rate under identical
seeds).

**Optional auxiliary:** at small L/K, compare ResearchParticleFilter marginals to a brute-force filter that uses the
**same** MC/closed-form LL (non-tautological vs physics). That auxiliary does not restore the old
soft-LL self-check.

The old tautological `tv_vs_exact` soft-LL Stage C path is **deleted or replaced**; tests must not
treat soft-self-consistency as a green Stage C.

Stages A and B remain as in FIL-11, extended to multi-rung masks under shared CRN (plan §4); P0/P1
Stage A fail under defaults remains allowed if documented.

## Alternatives considered

- **Keep soft-LL TV self-check as Stage C** — rejected: tautological; cannot catch soft-vs-physics
  divergence.
- **Drop Stage C entirely and rely only on A/B** — rejected: A/B do not prove the filter’s
  observation model is the same physics as the sim; ENG-02’s “shared kernels” claim needs an
  external generative check.
- **Only brute-force exact at toy L/K** — rejected as sole Stage C: useful auxiliary, but does not
  by itself prove agreement with `day_step` when the production LL is MC.

## Consequences

- Easy: a regression that reintroduces soft powers fails Stage C while sim kernels stay honest.
- Hard: tolerance X and discrete-obs binning must be chosen carefully so Monte Carlo noise does not
  flake CI; may need fixed seeds / more M draws in the check.
- Locked: M1.5 DoD requires generative Stage C green; M1 soft Stage C figures are historical, not
  the production gate.
- FIL-11 card text’s “exact comparison” clause is **elaborated**, not reopened: exact/brute-force
  remains allowed as auxiliary under the same LL as production.

**Depends on:** FIL-11, ADR 0087, ENG-02, MOD-12
**Supersedes (behaviourally):** M1 Stage C soft-LL TV interpretation in T-007 / `viz.fil11`
