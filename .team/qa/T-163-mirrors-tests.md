# T-163 mirrors shard — RED map (qa)

Ticket: **T-163** · Shard: **mirrors** · Branch: `team/T-163/qa` · Parent: `team/T-163/architect` @ `38df6ede`

Prove command:

```bash
cargo test -p voi_core --test t150_arrival_wire_filter_parity -- --nocapture
uv run pytest tests/test_docs_code_refs.py tests/test_studio_release_version.py \
  tests/test_rust_parity.py tests/test_simulator_belief_wire.py tests/test_t128_obs_channels.py \
  -v --no-cov
```

Result (2026-08-26): **RED** — 2 Rust failures + 11 Python failures (5 skipped: `_core` not built / retired skips).

## Coverage of acceptance criteria

- **S3.1 — Rust wire (`arrival_wire` / `belief_flat` / events)** → `crates/voi_core/tests/t150_arrival_wire_filter_parity.rs::t163_f3_events_wire_exports_three_per_lot_traces` — currently failing: `events_value` omits `temp_traces_by_lot`
- **S3.1** → `t150_arrival_wire_filter_parity.rs::t163_f2_events_wire_exports_per_lot_pack_dates` — currently failing: `events_value` omits `pack_dates_by_lot`
- **S3.1** → `tests/test_rust_parity.py::test_voi_core_filter_obs_has_per_lot_delivery_fields` — currently failing: `obs.rs` lacks `pack_dates_by_lot` / `temp_traces_by_lot` on `FilterObs` / `RichDay`
- **S3.1** → `tests/test_rust_parity.py::test_voi_core_events_wire_exports_per_lot_delivery_fields` — currently failing: `session.rs::events_value` JSON missing per-lot keys
- **S3.2 — Python mirror** → `tests/test_rust_parity.py::test_python_filter_types_expose_per_lot_delivery_fields` — currently failing: `filter/types.py` missing per-lot wire fields
- **S3.2** → `tests/test_t128_obs_channels.py::test_delivery_arrival_lot_ids_expect_three_lots_per_delivery` — currently failing: no `LOTS_PER_DELIVERY` / `lots_per_delivery` constant in `session.rs`
- **S3.3 — TypeScript mirror** → `tests/test_t128_obs_channels.py::test_typescript_rich_obs_wire_has_per_lot_delivery_fields` — currently failing: `obsMask.ts` / `engine/types.ts` lack `pack_dates_by_lot`
- **S3.3** → `tests/test_t128_obs_channels.py::test_f3_mask_keeps_per_lot_trace_array_not_scalar_only` — currently failing: `applyMask` still gates scalar `pack_date_days` only
- **S3.4 — Studio version bump** → `tests/test_studio_release_version.py::test_studio_package_version_is_0_7_2` — currently failing: `web/package.json` still `0.7.1`
- **S3.5 — Release guard** → `tests/test_studio_release_version.py::test_publishable_path_changes_require_strict_version_bump` — currently failing: publishable `crates/voi_core/` diff without semver bump
- **S3.6 — Code-ref citations** → `tests/test_docs_code_refs.py::test_in_the_code_tables_resolve` — currently failing: stale `mu_t` / `sigma_t` / `sample_truncated_normal` pins on `arrival.rs`
- **S3.6** → `tests/test_docs_code_refs.py::test_arrival_code_refs_do_not_cite_retired_truncated_normal_fields` — currently failing: retired symbols still cited in parameters / cold-chain docs
- **S3.6** → `tests/test_docs_code_refs.py::test_arrival_parameters_table_cites_v2_generative_symbols` — currently failing: parameters table missing `thermal_nodes` / `truth_transit_trace` / `t_break` / `legs`
- **S3.7 — Python parity** → `tests/test_rust_parity.py` source guards above + `test_engine_session_ten_day_trajectory_fixed_orders` (runtime; skipped when `_core` not built)
- **S3.8 — Wire parity** → same Rust `t163_*` events tests (v2 + multi-lot delivery wire)
- **S3.9 — Fit script sync** → owned by `qa-v2-artifact` shard (`tests/test_t163_arrival_fit.py`); not duplicated here

## Regression (expected green on architect tip)

- `t150_arrival_wire_filter_parity.rs::t150_wire_filter_parity_guard` — arrival chart law still matches filter (unchanged until v2 laws diverge wire path)
- `tests/test_simulator_belief_wire.py::test_belief_flat_wire_stays_f_native_without_tau_keys` — belief_flat export remains f-native
- `tests/test_simulator_belief_wire.py::test_belief_flat_does_not_embed_scalar_delivery_trace_fields` — delivery metadata stays off belief_flat

## Not covered by tests

- VitePress prose rewrite (`docs/store/cold-chain-arrival.md` body) — deferred per spec; citation re-pins only (S3.6)
- `web/src/charts/deliveryTempChart.ts` / `EventsPane.tsx` runtime render — covered indirectly via TS wire shape guards (S3.3); full browser smoke is verify/manual
- `scripts/fit_abdella_arrival.py` v2 schema (S3.9) — `qa-v2-artifact` shard
