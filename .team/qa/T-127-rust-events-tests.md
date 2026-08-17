# T-127 — RED test map (qa-rust-events)

## AC-rust-events

- session.rs dispatches events → `tests/test_t127_events_rpc.py::test_session_rs_dispatches_events_method`
- mask_for usage → `::test_session_rs_events_uses_mask_for`
- since_day required → `::test_events_requires_since_day`
- Response shape `{ days: [...] }` → `::test_events_returns_days_array_shape`
- P0 waste null not zero → `::test_events_p0_waste_is_null_not_zero`
- since_day slicing → `::test_events_since_day_slice`
- since_day > day → empty → `::test_events_since_day_gt_day_returns_empty`
- No session advance → `::test_events_does_not_advance_session_day`
