# 0087. Monte Carlo observation likelihood from shared day_step kernels

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-10 (M1.5 elaboration) / ENG-02
MILESTONE: M1.5 — filter complete across data-availability rungs

## Context

M1’s `_rbpf_update` scores particles with soft powers on picking/death probabilities plus Gaussian
match terms on sales/waste totals. That is not the law of MOD-08 Wallenius allocation or MOD-04
binomial deaths. Stage C’s TV-vs-exact check used the same soft likelihood, so TV≈0 was tautological.
FIL-10=A already chose bootstrap proposal specifically so we never need a Wallenius *density*.
ENG-02 / MOD-12 require sim and filter to import the same `model.day_step` kernels. M1.5 needs an
honest observation likelihood before any rung Stage A/B “pass” claim is VOI-ready.

## Decision

We will score masked `RichObs` fields with a **Monte Carlo observation likelihood** built from the
**same** kernels the simulator uses (`allocate_sales`, `death_prob_survival_ratio`, NB demand path /
`day_step`). For each particle (and optionally M forward draws):

1. Simulate forward day transition(s) from the particle’s latent state via shared kernels
   (bootstrap proposal remains “simulate allocation,” FIL-10=A — never evaluate Wallenius pmf).
2. Score only fields that are **present** under the mask (exact discrete likelihood where closed
   form exists; otherwise histogram/kernel density from M sims, or smoothed indicator match on
   counts).
3. Weight particles by that likelihood. Soft powers / Gaussian toy LL are removed from the
   production path.

Default production starts at **M=1** bootstrap-style weight; raise M only if ESS collapses and a
follow-on ADR records the change. Exact per-lot forward solvers at F1+ may later sit behind the
**same** log-likelihood interface and cross-check MC where both apply; M1.5 may ship MC-only first.

## Alternatives considered

- **Keep soft powers / Gaussian totals** — rejected: failed Stage A honesty narrative and made
  Stage C tautological against physics.
- **Closed-form Wallenius density for allocation LL** — rejected: FIL-10 deliberately avoids the
  1-D integral density; bootstrap only needs simulation.
- **Pluggable LL function per rung** — rejected: contradicts FIL-08=C (one model, masks).
- **Exact forward as the sole production LL** — rejected: only tractable at toy L/K; keep as
  auxiliary check, not the primary production path.

## Consequences

- Easy: Stage C can falsify “wrong physics”; ENG-02 shared-import regressions stay meaningful.
- Hard: MC LL costs `O(N · M · day)` and may need profiling; ESS monitoring becomes load-bearing
  (FIL-10 revisit trigger if ESS collapses).
- Locked: no new runtime dependencies for scoring (ADR 0084 / 0085 stack only); no Wallenius density
  in production.
- Gate: no rung Stage A/B “filter works” claims until this path is green (plan Phase 2).

**Depends on:** FIL-10, ENG-02, MOD-04, MOD-08, MOD-12, ADR 0086
**Does not claim:** P1 recovers age under defaults after the honest LL
