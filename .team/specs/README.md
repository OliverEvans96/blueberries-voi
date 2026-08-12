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
| [T-020](./T-020.md) | FIL-11 Stage C exact joint vs mean-field (FIL-04 check) | ADR 0090; evidence-only side path (does not replace M1.5 generative Stage C) |
| [T-021](./T-021.md) | Production RBPF → mean-field (FIL-13=B, FIL-04=C) | ADR 0091; wires `mean_field_update` + keeps MC LL weights |

Wave order: T-001 ∥ T-002 ∥ T-003 → T-004 → T-005 → (human FIL-13/15) → T-006 → T-007 → T-020 (additive MF evidence) → T-021 (production MF settle).

## M1.5 filter complete (2026-08-12)

Plan: [`.team/plans/M1.5-filter-complete.md`](../plans/M1.5-filter-complete.md).  
ADRs: [0086](../adr/0086-m15-richobs-unobserved-masks.md)–[0089](../adr/0089-m15-dynamic-l-sliding-window-fallback.md).  
Non-goals: no CTL, no VOI, no browser; do not reopen ⚑ cards.

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-008](./T-008.md) | ADR lock (docs only) | Plan; ADRs 0086–0089 |
| [T-009](./T-009.md) | Rich DayLog / SIM-04 emit | T-008 |
| [T-010](./T-010.md) | RichObs + UNOBSERVED + scenario masks | T-008 |
| [T-011](./T-011.md) | Honest MC observation likelihood | T-009, T-010 (**hard gate**) |
| [T-012](./T-012.md) | Stage C generative check | T-011 |
| [T-013](./T-013.md) | F2a pack-date prior + F2 age-at-receipt | T-010, T-011 |
| [T-014](./T-014.md) | F1/F1s lot-resolved likelihood | T-011 |
| [T-015](./T-015.md) | Dynamic L + joint→sliding_window fallback | T-011 |
| [T-016](./T-016.md) | Multi-rung Stage A (shared CRN) | T-013, T-014, T-015 |
| [T-017](./T-017.md) | Stage B + oracle ladder | T-016 |
| [T-018](./T-018.md) | M1.5 close-out | T-012, T-017 |
| [T-019](./T-019.md) | Sim emits ASN `pack_date` on DayLog (F2a Stage A unblock) | T-009, T-013, T-016; Oliver pack-date approval |

Wave order: T-008 → (T-009 ∥ T-010) → T-011 → T-012 → (T-013 ∥ T-014) → T-015 → T-016 → T-017 → T-018 → T-019.
