# CAL-01: Calendar realism (MWF cadence + FreshNet demand)

**Status:** COMPLETE — pending human merge to `main` (T-088 close-out)  
**Date:** 2026-08-13  
**Board / milestone:** CAL-01  
**Supersedes:** ADR [0011](../adr/0011-x-11-delivery-cadence-for-the-base-case.md) (daily) → [0112](../adr/0112-x-11-mwf-delivery-base-case.md); ADR [0031](../adr/0031-mod-09-demand-model.md) (i.i.d.) → [0113](../adr/0113-mod-09-calendar-demand.md)

## Decisions locked (Oliver)

| Topic | Lock |
|-------|------|
| Scientific landing | **New base case** — weekly cadence + calendar demand become defaults in sim, VOI, and web |
| Cadence | **Mon / Wed / Fri deliveries**, LT **1** → order **Sun / Tue / Thu** |
| Demand data | FreshRetailNet-50K (`Dingdong-Inc/FreshRetailNet-50K`); derived JSON product; optional `[freshnet]` for fit only |
| VOI pairing | Keep CRN: shared `(root_seed, PHYSICS_RUN_ID, day, :demand)` across knowledge scenarios |
| Physics tick | Stay **daily** `day_step`; non-order days force `order_qty=0`; UI jumps via `step_n` |
| Scale | FreshNet supplies **shape**; operational μ≈30; no yuan economics transfer |
| X-06 | Cadence-as-VOI-axis stays **parked** |

ADRs: [0112](../adr/0112-x-11-mwf-delivery-base-case.md) MWF · [0113](../adr/0113-mod-09-calendar-demand.md) calendar NB · [0114](../adr/0114-order-schedule-api.md) OrderSchedule · [0115](../adr/0115-freshnet-derived-demand-product.md) FreshNet product · [0116](../adr/0116-cal-01-track-ownership.md) ownership / `day=` shim.

## Architecture

```text
Wave 0 (serial)     Track A (schedule)     Track B (demand)      Track C (web)     Track D
T-076 ADRs/specs →  T-077 OrderSchedule ∥  T-078 FreshNet ingest
                    T-079 episode gate   ∥  T-080 fit profile
                    T-081 day controllers∥  T-082 draw_demand(day)
                    T-083 baselines/M2   ∥  T-084 CRN wire  ∥  T-085 Snapshot
                                                              T-086 next-order UI ∥ T-087 demand UI
                                                                                      → T-088 closeout
```

**Physics:** daily age → demand → allocate → spoil → deliver.  
**Orders:** only when `OrderSchedule.can_order(day)`; else qty 0.  
**Demand:** committed `demand_profile.json`; `draw_demand(..., day=)` owned by B3.

## Ticket map (binding IDs)

| Wave | Tickets | Logical | Parallelism |
|------|---------|---------|-------------|
| 0 | **T-076** | CAL-ADR | Serial architect (this tip) |
| 1 | **T-077** ∥ **T-078** | CAL-A1 ∥ CAL-B1 | Independent after T-076 |
| 2 | **T-079** ∥ **T-080** | CAL-A2 ∥ CAL-B2 | After A1 / B1 tips respectively |
| 3 | **T-081** ∥ **T-082** | CAL-A3 ∥ CAL-B3 | After A2 / B2; B3 owns `draw_demand(day=)` |
| 4 | **T-083** ∥ **T-084** ∥ **T-085** | CAL-A4 ∥ CAL-B4 ∥ CAL-C1 | After A3 / B3; C1 needs A2+B3 shapes |
| 5 | **T-086** ∥ **T-087** → **T-088** | CAL-C2 ∥ CAL-C3 → CAL-D1 | C2∥C3 after C1; D1 last |

### Ownership (ADR 0116)

| Track | Tickets | Owns |
|-------|---------|------|
| A | T-077, T-079, T-081, T-083 | `OrderSchedule`; episode/session gates; controllers; M2 gates |
| B | T-078, T-080, T-082, T-084 | `data/freshnet/`; fit; `draw_demand(day=)`; CRN demand wire |
| C | T-085, T-086, T-087 | `web/` Snapshot/config, next-order chrome, demand UI |
| D | T-088 | VOI smoke, changelog, milestone DoD |

**Shim:** T-079 may land before T-082 with `day=` optional; missing/`None` keeps prior μ behaviour.

## Orchestrator concurrency

1. After T-076 commit: fan out **qa T-077 ∥ qa T-078** on separate worktrees from architect tip.
2. After each qa tip: implement in its own worktree; then **reviewer ∥ verifier**.
3. One writer per worktree; eager cleanup of superseded role worktrees.
4. Merge track tips only on `team/CAL-01/*` or ticket branches (allowed); **never** merge to `main` (human).
5. Within a ticket: architect → qa → implement stays sequential.
6. Peak concurrency ≈ Wave 4 (3 implement + review/verify pairs).

```text
Time →
Wave0:  [T-076 Architect]
Wave1:  [T-077 …]  ∥  [T-078 …]
Wave2:  [T-079 …]  ∥  [T-080 …]
Wave3:  [T-081 …]  ∥  [T-082 …]
Wave4:  [T-083 …]  ∥  [T-084 …]  ∥  [T-085 …]
Wave5:  [T-086 …]  ∥  [T-087 …]  →  [T-088 closeout]
```

## Definition of done

- Acceptance criteria for T-077–T-088 pass under verify gates in `AGENTS.md`.
- `.team/reviews/` APPROVED for implement tips; `.team/qa/T-XXX.md` PASS; changelog entry for CAL-01.
- VOI smoke runs under MWF + calendar demand with CRN identity preserved across scenarios.
- Prior daily / i.i.d. citeable numbers flagged as requiring regeneration.
- FIL-13 remotesure note recorded if cadence changes measured L (T-088).

## Non-goals

- Reopening X-06 (cadence as VOI sweep axis) or VOI-02 honesty arms
- Full FreshNet two-stage latent demand recovery as production prior
- Changing filter joint/cohort production beyond a remotesure note
- Collapsing physics to weekly ticks
- Merging to `main` / editing `.github/workflows/`
- Transferring Chinese yuan prices or pack sizes into `ProfitCosts`

## Risks

- FreshNet normalized sales + opaque SKUs → document selection + scale; cite **shape**, not absolute units.
- Mar–Jun window ≠ full annual seasonality (ADR 0115 honesty).
- Periodic age + day-indexed baselines easy to forget — specs require tests for 3/3/4, H×7, day-indexed weights.
- Superseding X-11/MOD-09 invalidates prior citeable VOI under daily i.i.d. — changelog must say regen required.
- Channel mismatch (Dingdong instant-delivery vs Western MWF trucks) — transferability paragraph in ADR 0115.

## Key library touchpoints

- Schedule: new module; `sim/episode.py`, `simulator/day_driver.py`, `sim/__init__.py`
- Demand: `model/__init__.py` `ModelParams` / `draw_demand` / `day_step`; `data/freshnet/`
- Controllers: `damped_sw`, `rung0`, `toy_dp`, `rollout`, `ordering`; `sim/alpha_tune`, M2 gates
- VOI: `voi/crn.py` + CRN identity regression
- Web: `web/src/main.ts`, `controls.ts`, `charts/demandDist.ts`, `mock/generate.ts`
