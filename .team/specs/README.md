# Specs

Ticket specs live here as `T-XXX.md` (acceptance criteria, interfaces, out of
scope). Create them with `/ticket` or the write-spec skill after intake.

## M1 filter build (2026-08-12)

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-001](./T-001.md) | Scaffold, package layout, SIM-05 RNG | ADR 0074, 0068, 0084 |
| [T-002](./T-002.md) | Shared model kernels (`day_step`, Weibull, Q10, picking, allocation, demand) | MOD-04/07/08/09/12; ADR 0079–0081 |
| [T-003](./T-003.md) | Gate 0 + Abdella traces | ADR 0078, MOD-21 |
| [T-004](./T-004.md) | Arrival generator, forward sim, SIM-04 logging, cohort-count figure | T-002, T-003 |
| [T-005](./T-005.md) | FIL-13 runtime/accuracy bakeoff (A–E) | T-004; ADR 0082 PROPOSED |
| [T-006](./T-006.md) | Production RBPF (after FIL-13/15 settled) | T-005 + Oliver settle; ADR 0082/0083 |
| [T-007](./T-007.md) | FIL-11 staged validation A → B → C (hard stop if A fails) | T-006; ADR 0056 |
| [T-008](./T-008.md) | FIL-11 Stage C exact joint vs mean-field (FIL-04 check) | ADR 0086; evidence-only (no soft-LL / ⚑ ADR flip) |

Wave order: T-001 ∥ T-002 ∥ T-003 → T-004 → T-005 → (human FIL-13/15) → T-006 → T-007 → T-008.
