# T-C2-A QA — belief-policy shard RED map

Focused gates (2026-08-16):

- `cargo test -p voi_core belief_flat_from_unit_bank effective_inventory_f_belief damped_sw_order_f_belief -- --nocapture`
- `uv run pytest tests/test_damped_sw_f_policy.py --no-cov`

## Coverage of acceptance criteria

### AC-belief — `f_grid` / `f_marginals` wire

- `belief_flat_from_unit_bank` produces flat belief with `f_grid[K]` ∈ `[0, 1]`, `f_marginals` length `L×K` (row-major), and `lot_counts[L]`; rows are alive-only normalized marginals → `crates/voi_core/src/belief_flat.rs::belief_flat_from_unit_bank_exports_f_wire_keys` — currently failing: `unimplemented!("belief_flat_from_unit_bank")`
- `f_grid` endpoints and interior in `[0, 1]` → `belief_flat::belief_flat_from_unit_bank_f_grid_in_unit_interval` — currently failing: stub panics before export
- `lot_counts` count alive units (`f > 0`) per lot → `belief_flat::belief_flat_from_unit_bank_lot_counts_are_alive_only` — currently failing: stub panics
- Alive-only normalized row marginals (row-major `L×K`) → `belief_flat::belief_flat_from_unit_bank_marginals_row_major_and_normalized` — currently failing: stub panics
- Empty bank: zero counts, uniform marginals → `belief_flat::belief_flat_from_unit_bank_empty_bank_zero_counts_uniform_marginals` — currently failing: stub panics
- Weighted particles aggregate lot counts → `belief_flat::belief_flat_from_unit_bank_weighted_particles` — currently failing: stub panics
- Exported `K` matches session `k_dim` → `belief_flat::belief_flat_from_unit_bank_k_matches_session_k_dim` — currently failing: stub panics
- Python `FreshShelfBelief` export uses `f_grid` / `f_marginals` (not τ wire) → `tests/test_damped_sw_f_policy.py::test_f_belief_export_uses_f_grid_not_tau_grid` — currently failing: `FreshShelfBelief` not exported from `filter.belief`

### AC-policy — f-native inventory and ordering

- `effective_inventory_f_belief` = `Σ_lot lot_count_l × Σ_bin f_marginal[l,b] × f_grid[b]` plus pipeline term → `policy::effective_inventory_f_belief_matches_ef_weighted_sum` — currently failing: `unimplemented!("effective_inventory_f_belief")`
- Empty lots: pipeline-only term → `policy::effective_inventory_f_belief_empty_lots_pipeline_only` — currently failing: stub panics
- f-native inventory differs from Weibull `effective_inventory_belief` on same marginals → `policy::effective_inventory_f_belief_differs_from_weibull_tau_path` — currently failing: stub panics
- `damped_sw_order_f_belief` mirrors `damped_sw_order_belief` structure on f-belief → `policy::damped_sw_order_f_belief_matches_hand_formula` — currently failing: `unimplemented!("damped_sw_order_f_belief")`
- Non-order day returns zero → `policy::damped_sw_order_f_belief_non_order_day_zero` — currently failing: stub panics
- Positive-part yields zero when inventory covers quantile → `policy::damped_sw_order_f_belief_positive_part_zero_when_inventory_covers_quantile` — currently failing: stub panics
- Python f-policy path: `effective_inventory_f_belief` hand formula → `tests/test_damped_sw_f_policy.py::test_f_belief_effective_inventory_matches_ef_weighted_sum` — currently failing: `effective_inventory_f_belief` not exported
- Python f-policy path: empty shelf pipeline → `tests/test_damped_sw_f_policy.py::test_f_belief_effective_inventory_empty_lots_pipeline_only` — currently failing: `empty_f_shelf_belief` not exported
- Python f-policy path: damped SW order hand formula → `tests/test_damped_sw_f_policy.py::test_f_belief_damped_sw_order_matches_hand_formula` — currently failing: `blueberries_voi.controller.f_sw` module missing
- Python f-policy path: zero order when covered → `tests/test_damped_sw_f_policy.py::test_f_belief_damped_sw_zero_when_inventory_covers_quantile` — currently failing: `blueberries_voi.controller.f_sw` module missing

## Not covered by tests

- Snapshot / DayDelta `belief` from `EngineSession` contains `f_grid` / `f_marginals` (not `tau_grid` / `age_marginals`) — owned by **qa-session-wire** shard (`tests/test_rust_session_wire.py`); verify there.
- `rollout.rs` calls f-native `day_step` and f-belief export — owned by **impl-policy**; verify by diff + rollout integration tests after implement.
- Production `session.rs` `act` does not call `weibull_survival` or `effective_inventory_belief` — owned by **impl-session** + **qa-session-wire**; verify by `rg` guard in AC-bench-cleanup.
- Legacy τ `test_damped_sw_policy.py` rows below module skip — superseded for production path; remain skipped until human removes T-121 F3 skip or implementer gates them in AC-guards closeout.
