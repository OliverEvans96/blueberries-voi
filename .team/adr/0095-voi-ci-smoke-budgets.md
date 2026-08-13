# 0095. M3 CI smoke budgets vs production VOI defaults

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: VOI-04 / ENG-04 (M3 budgets)
GROUP: VOI
PROVENANCE: M3 Wave 0 lock
TIER: 2
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

VOI-04 locks a **fine β grid (10+ values)** and SIM-02 full CRN across scenarios. Running that at
production episode lengths with SW+rollout inside every CI job would make the suite unusable
(hours), while skipping an automated β=1 / wiring gate would let silent CRN or metric bugs reach
M3 close-out. M2 already used tiny `n_burn`/`n_score`/rollout budgets for ladder and multi-scenario
CI smokes — M3 needs the same explicit split.

## Decision

We will:

1. Document **production defaults** on the sweep API (fine β grid ≥10 including 1.0; burn-in and
   score horizon suitable for stationary profit; replication count for paired bootstrap) as the
   values experiments / humans use when generating headline figures.
2. Ship **CI smoke presets** (named constants or `smoke=True` / explicit tiny kwargs) with:
   - a **subset** of β values that **must include 1.0** and at least one β>1
   - tiny `n_burn`, `n_score`, `n_replications`, filter `N`, and rollout path/H budgets
3. Require automated tests to call the **smoke** preset (or equally tiny explicit kwargs), never
   the full production grid, inside `pytest`.
4. Keep production defaults reachable without a second API shape — same functions, different
   numeric budgets (mirrors M2 ladder / multi-scenario pattern).

## Alternatives considered

- **Always run the full fine grid in CI** — rejected: compute cost dominates; would pressure
  weakening coverage or skipping gates.
- **No automated VOI gate; notebook-only** — rejected: ENG-04 spirit and M2 precedent require CI
  red on broken β=1 / CRN / metric wiring.
- **Separate `voi_smoke` package or CLI-only path** — rejected: duplicates API surface; smoke must
  exercise the same code paths as production with smaller integers.

## Consequences

**Easy:** CI stays tractable; production experiments keep VOI-04 resolution.  
**Hard:** Authors must not cite smoke numbers as headline VOI; changelog / reports must say when
figures used production budgets.  
**Locked:** Tests that invoke the full fine grid × full rungs × long horizon are out of CI scope.  
**Revisit if:** Smoke budgets become so tiny that the β=1 gate is vacuous — then raise smoke
slightly, not the full production grid.
