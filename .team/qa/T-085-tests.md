# T-085 RED map — Web config Snapshot (schedule + demand summary)

## Coverage of acceptance criteria

- Snapshot / init config exposes schedule fields (order/delivery weekdays, lead
  time, epoch for weekday labels)  
  → `tests/test_t085_snapshot_schedule_demand.py::test_live_snapshot_exposes_schedule_fields`
  — currently failing: live `EngineSession` Snapshot has no `schedule`  
  → `…::test_live_snapshot_schedule_matches_default_order_schedule` — currently
  failing: same  
  → `…::test_live_snapshot_schedule_epoch_labels_monday0_weekdays` — currently
  failing: same  
  → `tests/test_simulator_schema.py::test_live_init_snapshot_validates_like_golden`
  — currently failing: golden documents `schedule` / `demand_summary`; live keyset
  does not

- Snapshot / config exposes demand profile summary (`scale_mu` + length-7 DOW
  series)  
  → `…::test_live_snapshot_exposes_demand_summary` — currently failing: no
  `demand_summary` on live Snapshot  
  → `…::test_live_demand_summary_scale_near_committed_profile` — currently failing:
  same  
  → `…::test_demand_summary_is_not_full_freshnet_blob` — currently failing: same

- Mock adapter populates coherent stubs when live engine is absent  
  → `web/src/engine/snapshotScheduleDemand.test.ts` › init Snapshot populates
  coherent schedule stubs — currently failing: `MockAdapter` Snapshot.schedule
  null  
  → `…` › init Snapshot populates demand_summary — currently failing:
  `demand_summary` null  
  → `…` › reset Snapshot keeps schedule and demand_summary stubs — currently
  failing: same

- Golden / contract tests updated; forbidden keys remain forbidden (ADR 0100)  
  → Golden fixture `tests/fixtures/simulator/snapshot_seed42.json` + README
  document `schedule` + `demand_summary`  
  → `…::test_snapshot_golden_documents_schedule_and_demand_summary` — **passing**
  (contract documentation)  
  → `…::test_fixture_readme_documents_schedule_and_demand_summary` — **passing**  
  → `tests/test_simulator_schema.py::test_golden_snapshot_validates_required_keys_and_flat_belief`
  — **passing** (asserts new keys on golden)  
  → `…::test_validate_snapshot_still_rejects_pnl_on_schedule_bearing_payload` —
  **passing** (ADR 0100 preserved)  
  → `…::test_live_snapshot_keyset_includes_golden_schedule_keys` — currently
  failing: live missing documented keys  
  → Schema shape guards: `…::test_validate_snapshot_rejects_schedule_with_out_of_range_weekday`,
  `…::test_validate_snapshot_rejects_demand_summary_with_wrong_dow_length`,
  `…::test_validate_snapshot_rejects_empty_order_weekdays` — currently failing:
  `validate_snapshot` does not yet validate schedule / demand_summary shape
  (DID NOT RAISE)

- Typecheck / unit tests for TS types  
  → `web/src/engine/snapshotScheduleDemand.typespec.ts` + vitest
  `typespec + tsc require ScheduleWire / DemandSummary on Snapshot` — currently
  failing: `tsc` errors — no `ScheduleWire` / `DemandSummary`; `schedule` not on
  `Snapshot`  
  → Mock unit tests above cover runtime stub AC

- Python export ruff/mypy on touched paths — **not covered by qa RED**; implement /
  verify role gates (`AGENTS.md`)

## Proven RED

```text
# From .worktrees/T-085-qa on team/T-085/qa
uv sync --all-extras --python 3.11
uv run --python 3.11 pytest tests/test_t085_snapshot_schedule_demand.py \
  tests/test_simulator_schema.py::test_golden_snapshot_validates_required_keys_and_flat_belief \
  tests/test_simulator_schema.py::test_live_init_snapshot_validates_like_golden \
  --no-cov -v
# 11 failed, 4 passed — failures are missing Snapshot.schedule / demand_summary
# on live EngineSession, missing schema validation of those fields, and live
# keyset vs updated golden (not import typos)

cd web && pnpm exec vitest run src/engine/snapshotScheduleDemand.test.ts
# 4 failed, 1 passed — missing ScheduleWire/DemandSummary types (tsc) and mock
# adapter stubs; forbidden-key guard still passes
```

## Not covered by tests

- Exact alternate key names (`dow_factors` vs `dow_means`, `lead_time` vs
  `lead_time_days`) — helpers accept either; implement documents one spelling in
  module / `web` types (spec open question).
- Next-order-day play button (T-086) and demand UI charts (T-087).
- Full suite / coverage ≥80% — verifier owns CI-parity gates.
- ASGI / Pyodide HTTP adapters emitting the new fields — covered indirectly once
  Python Snapshot export lands; mock + EngineSession are the C1 surfaces.
