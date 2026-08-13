# T-086 smoke — next-order-day advance via step_n (CAL-C2)

Automated unit proof: `web/src/calendar/nextOrderAdvance.test.ts` (zeros on
intervening non-order / skip days, qty on target) and
`web/src/engine/nextOrderDayUi.test.ts` (mock `step_n` + studio wiring).

## Advance skips non-order days

Primary play builds `step_n` orders with `buildStepNOrders` from Snapshot
`schedule.order_weekdays` + epoch:

| From day (weekday) | Orders vector | Lands on |
|--------------------|---------------|----------|
| 0 Mon | `[qty]` | 1 Tue |
| 1 Tue (order day) | `[0, 0, qty]` | 3 Thu |
| 4 Fri | `[0, qty]` | 6 Sun |
| 6 Sun (order day) | `[0, qty]` | 8 Tue |

Intervening non-order days receive `order_qty=0`; only the target order day
gets the staged qty. Physics stay daily; the UI jumps via `adapter.step_n`.

## Optional single-day step — omitted

A separate debug “Advance one day” control was **omitted** as not cheap enough
to keep in the play chrome without crowding the primary next-order path.
Single-day `adapter.step` remains on the EngineAdapter contract for adapters /
tests; studio primary play uses `step_n` only. Revisit if a debug toggle is
needed later.

## Checklist (mock / live)

- [ ] Mock (`VITE_ENGINE_ADAPTER=mock`): Advance to next order day skips
      intervening days; weekday label + delivery hint update.
- [ ] Http / Pyodide: same chrome; network/RPC shows `step_n` with padded
      orders (zeros then qty).

**Pass / fail:** unit RED→GREEN on implement tip (vitest calendar + nextOrderDayUi).
