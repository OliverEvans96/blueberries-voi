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

## M2 controller and multi-scenario (2026-08-12)

Plan: [`.team/plans/M2-controller.md`](../plans/M2-controller.md).  
ADRs: [0092](../adr/0092-controller-belief-api.md)–[0093](../adr/0093-day-profit-helper.md) (plus CTL-01–06 / SIM-01 already ACCEPTED).  
Prerequisite: T-021 DONE (`PRODUCTION_BACKEND=mean_field`).  
Non-goals: no VOI sweep; no Pyodide packaging / ENG-01; no joint production reopen; see also parked [M2-controller-agent-brief.md](../plans/M2-controller-agent-brief.md) (eventual compat only).

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-022](./T-022.md) | M2 ADR/spec lock (docs only) | T-021; ADRs 0092–0093 |
| [T-023](./T-023.md) | Belief API (`ShelfBelief`) | T-022; ADR 0092 |
| [T-024](./T-024.md) | Closed-loop driver + `Policy` | T-022 |
| [T-025](./T-025.md) | Day profit helper (`sim/profit.py`) | T-022; ADR 0093 |
| [T-026](./T-026.md) | `case_round` + constant order | T-022 |
| [T-027](./T-027.md) | Rung 0 corrected age-blind | T-025, T-026 |
| [T-028](./T-028.md) | CTL-01 damped SW | T-023, T-025, T-026 |
| [T-029](./T-029.md) | CTL-03 α tuning | T-024, T-027, T-028 |
| [T-030](./T-030.md) | Rollout + salvage (+ optional budgets) | T-024, T-025, T-028 |
| [T-031](./T-031.md) | Toy exact DP | T-028 |
| [T-032](./T-032.md) | Ladder + ENG-04 gates | T-029, T-030, T-031 |
| [T-033](./T-033.md) | Multi-scenario + L remeasure | T-032 |
| [T-034](./T-034.md) | M2 close-out | T-033 |

Wave order: T-022 → (T-023 ∥ T-024 ∥ T-025 ∥ T-026) → (T-027 ∥ T-028) → T-029 → (T-030 ∥ T-031) → T-032 → T-033 → T-034.

## M3 VOI sweep (2026-08-12)

Plan: [`.team/plans/M3-voi-sweep.md`](../plans/M3-voi-sweep.md).  
ADRs: [0094](../adr/0094-voi-package-layout.md)–[0096](../adr/0096-voi-scenario-columns.md) (plus VOI-01–04 / SIM-02–03 already ACCEPTED).  
Prerequisite: M2 verify tip (`T-022`–`T-034` DONE).  
Non-goals: no honesty/misspecification arms (VOI-02=A); no ENG-01 / Pyodide; no cadence/stagger axes (X-06=A).

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-035](./T-035.md) | M3 ADR/spec lock (docs only) | M2 tip; ADRs 0094–0096 |
| [T-036](./T-036.md) | VOI metric (%, $ vs P0) | T-035; ADR 0069 |
| [T-037](./T-037.md) | Outer-loop CRN cell | T-035; ADR 0065/0066 |
| [T-038](./T-038.md) | Paired bootstrap CI | T-035; ADR 0071 |
| [T-039](./T-039.md) | Sweep orchestrator (scenario × β) | T-036, T-037, T-038 |
| [T-040](./T-040.md) | Smoke artifact + β=1 gate + figure hook | T-039 |
| [T-041](./T-041.md) | M3 close-out | T-040 |

Wave order: T-035 → (T-036 ∥ T-037 ∥ T-038) → T-039 → T-040 → T-041.

## ENG-01 dual-runtime simulator (2026-08-12)

Plan: [`.team/plans/ENG-01-dual-runtime.md`](../plans/ENG-01-dual-runtime.md).  
ADRs: [0099](../adr/0099-eng-01-dual-runtime-ap.md)–[0102](../adr/0102-eng-01-api-asgi-session.md)
([0073](../adr/0073-eng-01-browser-simulator-scope.md) superseded).  
Locks: Pyodide=**prod**, API=**dev**; order common+Pyodide → API → D3; browser v1 =
sim+filter+controller (dialed budgets); Pyodide **314.0.4** / CPython **3.14.2**; CI 3.11+3.12+3.14.  
Non-goals: not full WASM A; not JS-only B as prod; no matplotlib/pyarrow in-browser; no
production-N-in-tab without budget dials; honesty/cadence ⚑ out.

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-042](./T-042.md) | Wave 0 ADR/spec lock (docs only) | ADRs 0099–0102; plan |
| [T-043](./T-043.md) | EngineSession + day driver + act / step_n | T-042; ADR 0100 (**∥ T-044**) |
| [T-044](./T-044.md) | Derived Abdella + browser extras | T-042; ADR 0101 (**∥ T-043**) |
| [T-045](./T-045.md) | Golden Snapshot/DayDelta fixtures | T-043 (after Wave 1 merge; **∥ T-046**) |
| [T-046](./T-046.md) | Slim wheel + GH Release + CI 3.14 | T-044 (**∥ T-045**) |
| [T-047](./T-047.md) | Pyodide worker RPC + budget smoke | T-045, T-046 |
| [T-048](./T-048.md) | Slice 1 close-out | T-047 |
| [T-049](./T-049.md) | API ADR/OpenAPI lock (docs; implement gated) | T-042 / ADR 0102 |
| [T-050](./T-050.md) | ASGI app wrapping EngineSession | Slice-1 green; T-049 (**∥ T-051**) |
| [T-051](./T-051.md) | API contract tests vs goldens | T-045, T-050 |
| [T-052](./T-052.md) | Slice 2 close-out | T-050, T-051 |
| [T-053](./T-053.md) | UI ADR: EngineAdapter + projector | Slice-2 or export ADR; mockup worktree |
| [T-054](./T-054.md) | ViewModelProjector + MockAdapter deltas | T-053 (**∥ T-055 ∥ T-056**) |
| [T-055](./T-055.md) | PyodideAdapter → Release wheel | T-047, T-053 |
| [T-056](./T-056.md) | HttpAdapter → local API | T-050, T-053 |
| [T-057](./T-057.md) | Wire studio (dev=HTTP, prod=Pyodide) | T-054, T-055, T-056 |
| [T-058](./T-058.md) | ENG-01 / Slice 3 close-out | T-057 |

Wave order: T-042 → (T-043 ∥ T-044) → (T-045 ∥ T-046) → T-047 → T-048 → (T-050 ∥ T-051) →
T-052 → T-053 → (T-054 ∥ T-055 ∥ T-056) → T-057 → T-058.
## Audit remediation (2026-08-12)

ADR: [0104](../adr/0104-audit-remediation-defaults.md).  
Base: `main` @ M2+M3 merge tip. Integration branch deferred to Phase 3 as
`team/audit-remediation` (git cannot nest role branches under a bare branch of
the same name).  
Non-goals: M3 compute reduction; RBPF count physics; Stage A honesty; ENG-01.

| Ticket | Title | Depends on / notes |
| --- | --- | --- |
| [T-042](./T-042-audit-remediation.md) | Unify `case_round` (nearest) | ADR 0104 |
| [T-043](./T-043-audit-remediation.md) | `DEFAULT_PROFIT_COSTS` + Abdella defaults + VOI α gate | ADR 0104; CTL-03 |
| [T-044](./T-044-audit-remediation.md) | MF sweeps=5, bakeoff stubs, backlog/doc hygiene | ADR 0104 |

Wave order: architect (this tip) → qa (all ACs) → (T-042 ∥ T-043 ∥ T-044 implement).

## In-flight reservations (2026-08-13)

See [ticket-adr-reservations-2026-08-13.md](../plans/ticket-adr-reservations-2026-08-13.md). Specs for these
streams may live only on their ticket branches until integrate.

| Stream | Tickets | ADRs | Plan |
| --- | --- | --- | --- |
| Arrival-only filter | **T-067–T-069** | **0105–0106** | on `team/T-067/architect` |
| ENG-01 dual-mode readiness | **T-070–T-075** | **0107–0108** | [ENG-01-readiness.md](../plans/ENG-01-readiness.md) |

Next free after both: **T-076+**, ADR **0109+**. Do not assign overlapping IDs.
