# T-140 — configurable delivery calendar (backend)

## Context

Week-calendar Studio widget: user toggles **delivery** weekdays; **order** weekdays are
derived server-side from lead time. Supersedes the fixed MWF clause in ADR 0114 (see ADR 0142).

## Acceptance criteria

- [ ] **AC-C1:** `derive_order_weekdays(delivery, lead_time)` in Python and Rust with formula
  `(delivery - lead_time + 7) % 7`, dedupe + sort; defaults `[0,2,4]` + LT=1 → `[6,1,3]`.
- [ ] **AC-C2:** `OrderSchedule.with_delivery` / `from_delivery` factory; defaults unchanged.
- [ ] **AC-C3:** RPC `configure` parses `delivery_weekdays` (params or `config`), re-derives
  order days; ignores client `order_weekdays`.
- [ ] **AC-C4:** Snapshot `schedule` + `applied_config.delivery_weekdays` match live schedule.
- [ ] **AC-C5:** PyO3 `PyEngineSession.init` accepts optional `delivery_weekdays`; Python
  `EngineSession` passes config through and uses live schedule in `schedule_wire`.
- [ ] **AC-C6:** Tests: `test_order_schedule.py` (LT 0/1/2, dedup, toggle), `schedule.rs` unit
  tests, `test_rust_session_wire.py` custom delivery case.

## Out of scope

- Frontend week-calendar UI (separate frontend shard).
- Changing default delivery set without explicit config.
