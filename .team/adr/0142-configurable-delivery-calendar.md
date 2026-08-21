# 0142. Configurable delivery weekdays (derived order calendar)

STATUS: ACCEPTED
DATE: 2026-08-21
TICKET: T-140 (calendar backend)
SUPERSEDES: ADR 0114 fixed-weekday clause (delivery set + LT dial)

## Context

Studio week-calendar widget needs a single backend source of truth for which weekdays
accept orders vs receive delivery. ADR 0114 locked MWF delivery and Sun/Tue/Thu orders at
LT=1; product now allows toggling delivery weekdays while keeping order days derived.

## Decision

- **`delivery_weekdays`**: client-configurable, monday0 integers 0–6, non-empty.
- **`order_weekdays`**: **never** accepted from clients; always derived:

  `order_weekday = (delivery - lead_time + 7) % 7` per delivery day, dedupe + sort.

- Shared helpers: `derive_order_weekdays` + `OrderSchedule.with_delivery` / `from_delivery`
  in Python (`sim/order_schedule.py`) and Rust (`schedule.rs`).
- WASM RPC `configure` / `init` reads `delivery_weekdays` from params or nested `config`;
  snapshot `schedule` and `applied_config.delivery_weekdays` reflect the live schedule.
- Defaults unchanged: delivery `[0,2,4]`, LT=1 → orders `[6,1,3]`.

## Consequences

**Easy:** frontend toggles delivery only; backend and PyO3 stay aligned.

**Hard:** any code assuming fixed MWF must use snapshot schedule, not literals.

**Revisit if:** multi-LT order protection rules change independently of delivery set.
