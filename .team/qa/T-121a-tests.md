# T-121a QA — RED test map (wire fidelity / Wave A)

Track **A1** (PyO3 wire), **A2** (RPC configure), **A3** (WASM hydrate). Python tests
prove PyO3 stub gaps; Rust RPC expectations below are **documented for implement** in
`crates/voi_core/src/session.rs` (qa does not edit production Rust).

## Coverage of acceptance criteria

### A1 — PyO3 delegation to `snapshot_value` / `day_delta_value`

- Init Snapshot exposes populated flat belief (`L=2`, `K=4`, non-zero `lot_counts`) → `tests/test_rust_session_wire.py::test_rust_init_snapshot_belief_lot_counts_nonempty` — currently failing: stub `py_belief` returns `L=0`, `K=0`, empty arrays
- Init Snapshot exposes schedule block → `tests/test_rust_session_wire.py::test_rust_init_snapshot_schedule_nonempty` — currently passing via Python `_coerce_snapshot` backfill (still fails native PyO3 below)
- Init Snapshot exposes demand_summary → `tests/test_rust_session_wire.py::test_rust_init_snapshot_demand_summary_nonempty` — currently passing via Python `_coerce_snapshot` backfill
- Init Snapshot exposes `live_lots` list key → `tests/test_rust_session_wire.py::test_rust_init_snapshot_live_lots_key_present` — currently passing (empty list at day 0 is valid)
- DayDelta after step has populated belief → `tests/test_rust_session_wire.py::test_rust_step_delta_belief_nonempty` — currently failing: stub `py_delta` belief empty
- DayDelta after arrival has non-empty `live_lots` → `tests/test_rust_session_wire.py::test_rust_step_delta_live_lots_nonempty_after_arrival` — currently failing: stub always returns `live_lots=[]`
- DayDelta `seq` is session counter → `tests/test_rust_session_wire.py::test_rust_step_delta_seq_is_session_counter_not_episode_day` — currently failing: stub sets `seq=episode_day`
- PyO3 init native wire includes schedule + demand_summary → `tests/test_rust_session_wire.py::test_pyo3_init_includes_schedule_and_demand_summary` — currently failing: `py_snapshot` omits keys
- PyO3 init native belief from session bank → `tests/test_rust_session_wire.py::test_pyo3_init_belief_delegates_to_session_bank` — currently failing: stub `py_belief`
- PyO3 step native live_lots after arrival → `tests/test_rust_session_wire.py::test_pyo3_step_delta_live_lots_nonempty_after_arrival` — currently failing: stub `py_delta`

### A2 — RPC init parses full config (Rust unit tests — implementer adds)

Expectations for new/extended tests in `crates/voi_core/src/session.rs` `mod tests`:

| Proposed Rust test | Asserts | Current gap |
| --- | --- | --- |
| `rpc_init_includes_schedule_and_demand_summary` | `handle_rpc(init)` result has non-empty `schedule.*` and `demand_summary.dow_means` length 7 | RPC already uses `snapshot_value()` — likely **green** once added; documents contract |
| `rpc_init_belief_lot_counts_positive_mass` | `sum(lot_counts) > 0` with filter enabled after init | Belief wired in core — likely **green**; guards regression vs PyO3 stub |
| `rpc_init_accepts_nested_config_shipments` | `params.config.shipments` + budgets configure session (`n_particles`, `H`, lead_time sync) | **RED**: init only reads top-level `seed`/`L`/`K`/`obs_scenario`, not nested config |
| `rpc_init_reset_sync_schedule_lead_time` | `result.schedule.lead_time_days == config.lead_time` | **RED**: schedule lead time drifts from `configure` |
| `rpc_step_live_lots_nonempty_after_arrival` | step×3 with order 8 → delta `live_lots` non-empty | Core physics wired — likely **green** via `day_delta_value` |

Existing RPC tests that partially cover A2 today:

- `rpc_init_result_has_flat_belief` — shape only, does not assert non-zero mass or schedule keys
- `rpc_step_includes_belief` — shape only after single step at day 0

### A3 — WASM demo hydrate

- Not covered by Python pytest in this track — verify via `packaging/wasm/worker.js` + browser/studio smoke after A3 implement.

## Not covered by tests

- **A3 WASM `prepare_demo_config` parity** — because JS worker is out of pytest scope; verify manually or via wasm integration harness after implement.
- **Bit-identical belief arrays vs Python** — structural parity only (ADR 0127); order-qty tolerance tests live in T-121b.

## RED proof command

```bash
uv sync --all-extras --python 3.11
cd crates/voi_py && uv run maturin develop --release
uv run pytest tests/test_rust_session_wire.py --no-cov -v
```

Expected: multiple failures on PyO3 stub belief / live_lots / seq; schedule+demand_summary EngineSession tests may pass via Python backfill until A1 lands.
