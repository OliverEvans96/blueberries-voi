# 0091. Production RBPF age backend is mean-field (FIL-13=B); FIL-04 → C

STATUS: SUPERSEDED BY 0105
DATE: 2026-08-12
BOARD-ID: FIL-13 / FIL-04 (production settle)
GROUP: FIL
PROVENANCE: settle from FIL-11 Stage C PASS + Oliver Phase 0 lock
TIER: 1
MILESTONE: M1.5 — filter complete across data-availability rungs

## Context

FIL-13 bakeoff (ADR 0082) locked production at **E — `full_joint`** because measured open-loop
`L` was small enough that `K^L·N` fit the joint float budget. ADR 0089 then kept full joint as the
default and auto-fell back to `sliding_window` when the budget tripped. Both decisions assumed
**FIL-04=B (joint)** and **FIL-12=B (coarse joint)** remained the production age factorisation.

FIL-11 Stage C under ADR 0090 (`sequential_wor_pmf`, exact joint vs mean-field on fixed counts)
**passed** the freeze gates (report
[`.team/reports/FIL-11-stage-c-mf-findings.md`](../reports/FIL-11-stage-c-mf-findings.md) §6):
marginal TV and decision agreement support mean-field for production age belief. The settle note
recommended FIL-04 → **C** and aligning FIL-13 production with bakeoff arm **B (`mean_field`)**,
parking further investment in joint as the default path.

Production still scores particles with Monte Carlo observation likelihood (ADR 0087) and still
needs lot-map age updates at F1/F1s (T-014). Age *belief* updates under P1 totals (lot maps
`UNOBSERVED`) must use the real
`blueberries_voi.filter.age_likelihood.mean_field_update`, not the FIL-13 bakeoff factorised stub.

## Decision

We will:

1. Set **production FIL-13 = B (`mean_field`)**. `PRODUCTION_BACKEND == "mean_field"`; a default
   `RBPF()` constructs / names the `mean_field` backend.
2. **Reopen FIL-04 to C — mean-field, validated by brute-force Stage C** (ADR 0049 superseded by
   this settle). Card recommendation and Stage C evidence now agree.
3. Treat **FIL-12 (ADR 0057)** as **historical**: joint / coarse-joint tractability pressure is
   parked; it is no longer the production age-posterior path.
4. **Supersede production defaults** in ADR 0082 (E at measured L) and ADR 0089
   (joint→`sliding_window` fallback). Production **always** selects `mean_field` — there is **no**
   `K^L·N` gate on the production path and **no** silent `L` truncation.
5. Wire **real** `mean_field_update` into the production age step for **P1-style** updates: when
   sales/waste totals are observed and `sales_by_lot` / `waste_by_lot` are `UNOBSERVED`, each
   particle’s age marginals `(L, K)` are updated via `mean_field_update`.
6. Keep **`observation_loglik_mc`** as the particle **weight** score (ADR 0087 unchanged).
7. When lot maps are present (F1/F1s), keep **`_apply_lot_map_age_update`** (do not replace that
   path with MF totals-only updates).
8. Retain bakeoff registry arms **A–E** (`sliding_window`, `mean_field`, `bound_L`,
   `bootstrap_pf`, `full_joint`). The **`full_joint` memory guard** applies to the **bakeoff
   `full_joint` arm only**, not to production selection.
9. Add **no new runtime dependencies**.

## Alternatives considered

- **Keep FIL-13=E (`full_joint`) + ADR 0089 fallback** — rejected: Stage C PASS supports MF;
  joint budget / dynamic-L fallback complexity is unnecessary once factorisation is accepted for
  production.
- **Production default `sliding_window` (FIL-13=A)** — rejected: Stage C validated mean-field vs
  exact joint, not window vs joint; A remains bakeoff/fallback research, not the settle choice.
- **Replace MC particle weights with `sequential_wor_pmf`** — rejected for this ticket: ADR 0087
  stays the weight path; MF age update and MC LL are complementary, not a swap.
- **Flip FIL-04 without wiring production** — rejected: evidence without a production backend
  change leaves Stage A/B and VOI on the old joint-budget path.
- **Silent L truncation when joint would OOM** — rejected: still forbidden; under MF production
  the joint float gate is simply not applied.

## Consequences

**Easy:** production scales as `O(L·K·N)` for age marginals; long-dwell / high-`L` cells no longer
trip production on `MAX_JOINT_FLOATS`; Stage C evidence and production factorisation agree.

**Hard / cost:** residual cross-lot dependence (Stage 3 MI drift under stress) is accepted for
production; if belief-sensitive VOI later fails under MF, a **new** ADR must reopen toward window
or joint — this settle does not keep a silent joint fallback in production.

**Locked in:** `PRODUCTION_BACKEND = "mean_field"`; FIL-04=C; FIL-12 historical; 0082/0089
production defaults superseded; MC LL for weights; real `mean_field_update` on P1 UNOBSERVED maps;
lot-map update retained when maps present; bakeoff A–E retained with joint guard on E only.

**Revisit when:** VOI / multi-step controller metrics show MF-induced belief error that changes
decisions, or Stage C–style gates fail under a new observation law.

**Depends on:** ADR 0090 (Stage C evidence), ADR 0087 (MC LL), T-014 (lot maps), T-020

**Milestone:** M1.5 — filter complete across data-availability rungs

**Ticket:** T-021
