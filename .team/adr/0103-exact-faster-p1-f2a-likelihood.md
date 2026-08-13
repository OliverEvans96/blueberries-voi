# 0103. Exact-faster P1/F2a likelihood via unique-particle MF dedup + NumPy sequential-WOR DP

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: *(repo)* / M3 compute
GROUP: FIL / VOI
PROVENANCE: M3 compute-reduction shortlist (exact-first)
TIER: 2
MILESTONE: M3 — VOI sweep, oracles, misspecification arms

## Context

Production M3 VOI wall-clock is dominated by the **exact** ADR 0090 density inside
`mean_field_update` for **P1** and **F2a** (totals MF path). Profiling and closed-loop
probes (`.team/reports/M3-compute-reduction-brainstorm.md`, plain-language companion)
put ~99% of that hot path in `sequential_wor_composition_probs` called repeatedly from
per-particle MF in `_rbpf_update`. After resampling, many particles share identical
`(counts, age_post)` and today each still pays a full MF update.

ADR 0090 locks the named sequential-WOR density; ADR 0091 wires real MF into production;
ADR 0084 forbids new runtime deps without a justifying ADR. Surrogate / multinomial LL
and Numba/Cython would change fidelity or the dep surface and are **not** this decision.

## Decision

We will keep the **exact** ADR 0090 sequential-WOR composition density and speed the
P1/F2a MF path **only** by:

1. **Unique-particle MF dedup** in `_rbpf_update`: group particles with identical
   `(counts[i], age_post[i])` (fingerprint: `tuple(counts[i].tolist())` +
   `age_post[i].tobytes()`), run `mean_field_update` once per unique key, broadcast
   posteriors to duplicates.
2. **NumPy rewrite** of `sequential_wor_composition_probs` implementing the **same**
   sequential-WOR DP recurrence (fixed weights among nonempty cohorts matching
   `allocate_sales`) — no public API change.
3. **No surrogate math**, **no new runtime dependencies** (ADR 0084). Optional
   bit-identical call-level memo of LL/DP *within* a single `mean_field_update` is an
   allowed thin win if posteriors stay identical.

Tickets: **T-064** (dedup), **T-065** (NumPy DP), **T-066** (re-benchmark report).

## Alternatives considered

- **Multinomial / moment-matched surrogate LL for VOI** — rejected for this stream:
  changes the named density (ADR 0090); MOD-08 already rejected with-replacement near
  clear shelves; requires a separate ADR + honesty banner if ever needed.
- **Numba / Cython compiled DP** — rejected for now: new runtime dep vs ADR 0084;
  revisit only if NumPy + unique-MF still leave the sweep intractable.
- **Fewer MF sweeps, cut N/reps/β, defer F2a, cheap-control belief, cell parallelism as
  the primary fix** — rejected as the *decision* here: those are separate experiment /
  budget knobs; this ADR locks exact-math speedups on the density path first.

## Consequences

**Easy:** Same posteriors and same public density API; VOI fidelity stays tied to
FIL-11 / ADR 0090; implementers stay on numpy/scipy only.

**Hard / cost:** Dedup and NumPy DP are engineering work with careful numeric-identity
tests; speedup is workload-dependent (unique-particle rate after resample) and may still
leave a multi-day full grid — surrogate or Numba may return later under a **new** ADR.

**Locked in:** Production default LL remains exact sequential-WOR; no silent surrogate;
no numba/cython without ADR.

**Revisit when:** Post T-066 benches show exact path still too slow for the citeable
sweep, or bit-identity cannot be held under float64 DP reshape.

**Depends on:** ADR 0084, 0090, 0091; reports `M3-compute-reduction-*`

**Milestone:** M3 — VOI sweep

**Tickets:** T-064, T-065, T-066
