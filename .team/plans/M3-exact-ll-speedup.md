# M3 exact LL speedup (T-064 / T-065 / T-066)

**Status:** architect lock via ADR 0097 (2026-08-12)  
**Audience:** qa → implement → review → verify  

## Why

VOI wall-clock is dominated by exact sequential-WOR composition inside P1/F2a
mean-field age updates. Evidence and ranked shortlist:

- [`.team/reports/M3-compute-reduction-brainstorm.md`](../reports/M3-compute-reduction-brainstorm.md)
- [`.team/reports/M3-compute-reduction-plain-language.md`](../reports/M3-compute-reduction-plain-language.md)

## Ticket split

| Ticket | Work |
|--------|------|
| **T-064** | Unique-particle MF dedup in `_rbpf_update` |
| **T-065** | NumPy rewrite of `sequential_wor_composition_probs` (same DP) |
| **T-066** | Re-bench → `.team/reports/M3-exact-ll-speedup-bench.md` |

## In / out

**In:** exact ADR 0090 density; unique-MF + NumPy DP; optional bit-identical LL/DP memo inside MF.  
**Out:** multinomial/surrogate LL; Numba/Cython; fewer MF sweeps; cut N/reps/β; defer F2a; cheap-control belief; cell parallelism.

## ADR

[0097](../adr/0097-exact-faster-p1-f2a-likelihood.md) — no new runtime deps (0084).
