# 0082. FIL-13: Tractability restore — full joint (E) at measured L

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: FIL-13
GROUP: FIL
PROVENANCE: newly-raised; settled from T-005 bakeoff
TIER: 1
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

FIL-12=B chose a coarse joint age grid so `K^L` stays small, on a worked example with **L ≈ 4**.
Board numbers previously suggested **L ≈ 12–20** under MOD-13=C + daily delivery, which would make
`K^L` infeasible. FIL-13 required an in-repo bakeoff before locking production RBPF shape.

## Decision

**E — Keep FIL-12=B / full joint** is the production tractability backend **at measured L**.

Evidence from T-005 (`experiments/fil13_bakeoff.md`, `figures/m1/fil13_runtime.png`):

- Under interim M1 defaults (open-loop S=60, case size 8, σ=0.5, FIL-14 extinction), empirical
  live-cohort counts are **p50≈2, p90≈3, max≈3** — far below the 12–20 board estimate.
- At L≤3 and production (K=8, N=2000), `K^L·N ≈ 1.0×10^6` ≪ budget `5×10^7`, so full joint is
  tractable.
- The user/board rule was: prefer **A (sliding_window)** if L is large; choose **E** when empirical
  L is small enough. Measured L qualifies for E.
- **A** remains implemented as the bakeoff/fallback backend if a future policy regime pushes L up
  and trips the memory guard.

Oliver was not available for interactive settle mid-flight; this ADR records the evidence-backed
choice so T-006 can proceed.

## Alternatives considered

| Key | Option | Outcome |
| --- | --- | --- |
| **A** | Sliding window + factorised tail | Preferred if L large; retained as fallback, not needed at measured L |
| **B** | Mean-field | Bakeoff/diagnostic only |
| **C** | Bound live cohort count | Rejected for production sim |
| **D** | Bootstrap PF (age in particle) | Bakeoff arm only |
| **E** | Full joint (FIL-12=B) | **Accepted** — feasible at measured L |

## Consequences

- Production `RBPF` uses full-joint age posterior at the configured L (guard still fires if
  `K^L·N` exceeds budget — no silent truncation).
- If a later controller/cadence regime raises L so the guard trips, reopen this ADR toward A.
- FIL-15 locks K/N/ESS for the E path.

**Depends on:** `FIL-12`, `MOD-13`, `X-11`, `MOD-07`, `FIL-14`, `MOD-25`, `MOD-26`, T-005

**Milestone:** M1 — filter recovers truth from synthetic P1 data
