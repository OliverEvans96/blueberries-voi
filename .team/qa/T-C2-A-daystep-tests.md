# T-C2-A-daystep — RED test map (qa-daystep shard)

## Coverage of acceptance criteria

### AC-daystep — f-native ground truth (`day_step`)

- `day_step` advances `L×U` freshness with gamma decrement (no `q10_age_increment` τ bump, no `death_prob_survival_ratio` Weibull spoil on production path)
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_exports_unit_day_step_api` — currently failing: `UnitDayStepIn` / `unit_day_step` not implemented; legacy Weibull/q10 paths still present
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_gamma_aging_deterministic` — currently failing: gated on f-native API
  - `tests/test_f_native_day_step.py::test_day_step_f_native_exports_unit_day_step_api` — currently failing: source contract `UnitDayStepIn` missing

- Units with `f ≤ 0` after aging are dead; alive count per lot equals `#{f > 0}` in that lot's segment
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_alive_count_is_positive_f_slots` — currently failing: gated on f-native API
  - `tests/test_f_native_day_step.py::test_day_step_f_native_scripted_grid_fixture_shape` — currently failing: gated on f-native API

- Sales allocation calls `picking_weights_f` on alive units, zeros picked slots; `RichDay` / `DayStepOut` aggregates match summed unit events
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_physics_exports_picking_weights_f` — currently failing: `picking_weights_f` not in `physics.rs`
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_picking_weights_f_monotone_normalized` — currently failing: `picking_weights_f` not implemented
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_picking_zeros_picked_slots` — currently failing: gated on f-native API
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_aggregates_match_unit_events` — currently failing: gated on f-native API
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_conservation_scripted_seed` — currently failing: gated on f-native API
  - `tests/test_f_native_day_step.py::test_day_step_f_native_picking_weights_f_reference_monotone` — currently failing: `picking_weights_f` not in `physics.rs`
  - `tests/test_f_native_day_step.py::test_day_step_f_native_conservation_rust_tests_pass` — currently failing: Rust `day_step_f_native_*` tests do not pass

- Delivery injects `units_per_lot` (default **15**) units with `f` from arrival prior
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_delivery_injects_units_per_lot_default_15` — currently failing: gated on f-native API
  - `crates/voi_core/src/day_step.rs::f_native_day_step_spec::day_step_f_native_delivery_f_from_arrival_prior` — currently failing: gated on f-native API
  - `tests/test_f_native_day_step.py::test_day_step_f_native_delivery_defaults_units_per_lot_15` — currently failing: gated on f-native API

- `cargo test -p voi_core day_step` and physics fixtures pass with conservation on scripted seeds
  - `tests/test_f_native_day_step.py::test_day_step_f_native_conservation_rust_tests_pass` — currently failing: full Rust shard not green

## Not covered by tests

- Temperature-scaled gamma draw distribution parameters (beyond deterministic `gamma_decrement` injection) — verify by implementer unit tests on `gamma_decrement_for_store` once added; qa uses fixed decrement for scripted conservation.
- F2a Gaussian pack-date birth path end-to-end — verify by `impl-daystep` integration with `age_at_receipt` / pack-date metadata; qa covers Dirac `delivery_f` and `generate_arrival_age` default path.
