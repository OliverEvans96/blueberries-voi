# 0089. Dynamic L + joint→sliding_window fallback when budget trips

STATUS: SUPERSEDED BY 0091
DATE: 2026-08-12
BOARD-ID: FIL-13 (M1.5 long-dwell policy)
MILESTONE: M1.5 — filter complete across data-availability rungs

## Context

**Production default superseded by ADR [0091](./0091-fil13-production-mean-field.md):** production
always selects `mean_field` (no joint→`sliding_window` production fallback). Dynamic-L tracking may
still matter for state dimension; the joint float gate is not a production selector.

FIL-12=B (⚑) locks coarse-grid **full joint** age posteriors; do not reopen without Oliver.
FIL-13=E accepted full joint at **measured** M1 L (p50≈2, max≈3) with `MAX_JOINT_FLOATS` guard that
raises rather than silently truncating L. Production RBPF still hard-codes `PRODUCTION_L=3`.
Long-dwell verification cells push empirical live cohorts to L≈7–8, which trips `K^L·N` against the
budget. Sliding-window (bakeoff backend A) is already implemented and was named in ADR 0082 as the
fallback if a future regime raises L — but M1 only **raises** on budget trip; it does not auto-select
the fallback.

## Decision

We will keep **full_joint** as the production default while
`joint_state_count(K, L, N) ≤ MAX_JOINT_FLOATS`.

When configured or empirical live-cohort count `L` would exceed the budget:

1. **Auto-fallback to `sliding_window`** (existing bakeoff backend A), with a **logged reason**
   (K, L, N, joint float count, chosen backend).
2. **Do not silently truncate L** (FIL-13 guard rule remains).
3. Re-measure L under M1.5 open-loop and long-dwell verification cells; record in experiment MD.
4. Prefer **dynamic L** (track live cohorts / configured max) over a forever-fixed `PRODUCTION_L=3`
   when the joint backend is active and within budget.

This does **not** reopen FIL-12=B; sliding_window is the **pre-approved FIL-13 fallback**, not a
silent contradiction of the joint default.

## Alternatives considered

- **Always raise MemoryError when budget trips (M1 behaviour)** — rejected for M1.5 verification:
  long-dwell cells must still run; hard fail blocks Stage A across rungs without a documented
  tractability path.
- **Silently truncate L to fit budget** — rejected: explicitly forbidden by FIL-13 / ADR 0082.
- **Reopen FIL-12 toward mean-field or bound-L as production default** — rejected: ⚑ / settled
  without Oliver; out of M1.5 scope.
- **Always run sliding_window** — rejected: at measured L full joint is preferred and already
  validated by the FIL-13 bakeoff.

## Consequences

**Historical (pre-0091):** long-dwell cells could complete via joint→window fallback; production
default remained joint when budget allowed.

**Active (ADR 0091):** production `choose_backend` always returns `mean_field`; bakeoff may still
exercise window/joint arms; FIL-12 joint path is historical.

**Depends on:** FIL-12, FIL-13 (ADR 0082), FIL-15, `MAX_JOINT_FLOATS` in `filter.types`
**Superseded by:** ADR 0091 (production mean-field)
