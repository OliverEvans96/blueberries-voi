# T-150 — RED criterion → test map (qa)

Recorded after focused RED runs on `team/T-150/qa` (2026-08-22).

## Commands run (RED evidence)

```bash
# Rust (focused integration tests only)
cargo test -p voi_core --test t150_phase1_terminology --test t150_phase2_arrival_model --no-fail-fast
# → phase1: 1 passed, 6 failed | phase2: 2 passed, 17 failed

# Python 3.11 (focused file only)
uv run --python 3.11 pytest tests/test_t150_arrival_model.py -v
# → 5 failed, 1 passed, 3 skipped (_core not built)

# Web (focused vitest file only)
cd web && npm test -- src/t150_arrival.test.ts
# → 8 failed
```

### Excerpt — Rust phase 1 (representative)

```
test ac1_1_age_at_receipt_absent_from_live_path ... FAILED
  RED: age_at_receipt must be removed from crates/voi_core/src
test ac1_7_age_at_receipt_inert_on_production_delivery_path ... ok
```

### Excerpt — Rust phase 2 (representative)

```
test ac2_3_shape_scaling_spread_at_old_params ... FAILED
  RED: sd 0.173 must match shape-scaling 0.141, not scale-scaling 0.176
test ac2_4_reference_life_invariant_and_eta_choke_point ... FAILED
  RED: default must satisfy k*theta*eta_ref == 1; got 2.24
test ac2_11_f2_marginals_differ_from_p0 ... FAILED
  assertion `left != right` failed (flat ladder — bc26218 regression)
test ac2_2_gamma_additivity_and_timestep_invariance ... ok  # target math only
test ac2_11_p0_p1_posteriors_differ ... ok  # already holds today
```

### Excerpt — Python

```
FAILED test_ac2_6_arrival_artifact_committed_schema
  RED: data/abdella/arrival_model.json must exist
SKIPPED test_ac2_17_python_rust_arrival_artifact_parity
  blueberries_voi._core not built
PASSED test_ac1_3_python_legacy_paths_allowlisted
```

### Excerpt — Web

```
× AC1.5: StoreChartTabs tab label has no age framing
  expected not to match /Age & spoilage/
× AC3.2: dead studio knobs wired or removed
  RED: studio knob spread_scale must be wired in session.rs or removed from web
```

## Coverage of acceptance criteria

### Phase 1 (7 criteria)

| ID | Test | RED mode |
|----|------|----------|
| AC1.1 | `crates/voi_core/tests/t150_phase1_terminology.rs::ac1_1_age_at_receipt_absent_from_live_path` | **assertion failure** — `age_at_receipt` still in `obs.rs`, `day_step.rs`, `session.rs`, `web/src/` |
| AC1.2 | `t150_phase1_terminology.rs::ac1_2_f_scalar_helpers_and_branch_removed` | **assertion failure** — `f_at_receipt_from_age`, `birth_f_f2_dirac`, `delivery_birth_f` branch remain |
| AC1.3 | `t150_phase1_terminology.rs::ac1_3_effective_age_grep_guard_with_allowlist` + `tests/test_t150_arrival_model.py::test_ac1_3_python_legacy_paths_allowlisted` | **assertion failure** (Rust/web) — `age_marginal`, `effective age` on live paths; Python allowlist **passes** |
| AC1.4 | `t150_phase1_terminology.rs::ac1_4_freshness_identifier_renames` + `web/src/t150_arrival.test.ts` AC1.4 CSS | **assertion failure** — `ageMarginalFromFlat`, `age-young`, etc. still present |
| AC1.5 | `t150_phase1_terminology.rs::ac1_5_user_visible_strings_no_age_framing` + `web/src/t150_arrival.test.ts` AC1.5 | **assertion failure** — `"Age & spoilage"`, `age-spoilage`, DayInspector age-bin copy |
| AC1.6 | `t150_phase1_terminology.rs::ac1_6_exposure_language_in_doc_comments` | **assertion failure** — `physics.rs` / `params.py` still use age framing |
| AC1.7 | `t150_phase1_terminology.rs::ac1_7_age_at_receipt_inert_on_production_delivery_path` | **passes today** — pins inertness when `delivery_lambda` + `delivery_f` set; numeric no-regression for phase 1 verified by implementer via `git diff` (no golden edits) |

### Phase 2 (17 criteria)

| ID | Test | RED mode |
|----|------|----------|
| AC2.1 | `t150_phase2_arrival_model.rs::ac2_1_gamma_shape_scaling_not_scale` | **assertion failure** — `gamma_decrement_scale` still exported; shape not scaled in `for_params` |
| AC2.2 | `t150_phase2_arrival_model.rs::ac2_2_gamma_additivity_and_timestep_invariance` | **passes** — pure math target for shape-scaling (no production code yet) |
| AC2.3 | `t150_phase2_arrival_model.rs::ac2_3_shape_scaling_spread_at_old_params` | **assertion failure** — empirical sd ≈0.173 (scale-scaling), not 0.141 at k=2, θ=0.08 |
| AC2.4 | `t150_phase2_arrival_model.rs::ac2_4_reference_life_invariant_and_eta_choke_point` | **assertion failure** — k·θ·η_ref = 2.24; `set_reference_life` absent |
| AC2.5 | `t150_phase2_arrival_model.rs::ac2_5_transit_shelf_exposure_relationship` | **assertion failure** on recalibrated pin (2·3^0.1/14 ≈ 0.159); ratio assertions use committed params |
| AC2.6 | `t150_phase2_arrival_model.rs::ac2_6_arrival_artifact_schema` + `test_t150_arrival_model.py::test_ac2_6_*` | **assertion failure** — artifact / `arrival.rs` / PROVENANCE section missing |
| AC2.7 | `t150_phase2_arrival_model.rs::ac2_7_single_embed_and_parity` | **assertion failure** — zero embeds in `crates/voi_core/src` |
| AC2.8 | `t150_phase2_arrival_model.rs::ac2_8_calibration_note_script_exists` + `test_t150_arrival_model.py::test_ac2_8_calibration_note_script_and_outputs` | **assertion failure** — script and `calibration_note.md` absent |
| AC2.9 | `t150_phase2_arrival_model.rs::ac2_9_arrival_conditional_law_analytic` | **assertion failure** — `arrival.rs` missing; inline MC vs `gamma_p`/`gamma_q` baseline included |
| AC2.10 | `t150_phase2_arrival_model.rs::ac2_10_monotone_ladder_variance` | **assertion failure** — no artifact / variance helpers |
| AC2.11 | `t150_phase2_arrival_model.rs::ac2_11_f2_marginals_differ_from_p0`, `ac2_11_caught_up_f2_not_collapsed_to_p0`, `ac2_11_p0_p1_posteriors_differ` | **assertion failure** (F2/P0/catch-up); P0≠P1 **passes** today |
| AC2.12 | `t150_phase2_arrival_model.rs::ac2_12_within_lot_arrival_f_spread` | **assertion failure** — truth path still uses `delivery_birth_f`; `live_lots` lacks spread fields |
| AC2.13 | `t150_phase2_arrival_model.rs::ac2_13_filter_obs_no_freshness_valued_arrival` | **assertion failure** — `FilterObs.age_at_receipt` / `f_at_receipt` still present |
| AC2.14 | `t150_phase2_arrival_model.rs::ac2_14_truth_path_f_native_arrival` | **assertion failure** — `f_to_age` round trip and `birth_f_units_gamma` on truth path |
| AC2.15 | `t150_phase2_arrival_model.rs::ac2_15_filter_path_and_shipments_cleanup` | **assertion failure** — `resolve_arrival_lambda` and superseded `shipments.rs` helpers remain |
| AC2.16 | `t150_phase2_arrival_model.rs::ac2_16_lambda_floor_finite_cdf` | **assertion failure** — `arrival.rs` floor not implemented (analytic `gamma_p`/`gamma_q` baseline passes) |
| AC2.17 | `t150_phase2_arrival_model.rs::ac2_17_rust_embed_parses_committed_artifact` + `test_t150_arrival_model.py::test_ac2_17_python_rust_arrival_artifact_parity` | **assertion failure** / **skipped** — no `pub mod arrival`; PyO3 parity blocked until `_core` built |

### Phase 3 (8 criteria)

| ID | Test | RED mode |
|----|------|----------|
| AC3.1 | `test_t150_arrival_model.py::test_ac3_1_arrival_product_changes_engine_physics` | **skipped** (`_core` not built) — will assert different `arrival_summary` per `arrival_product` |
| AC3.2 | `web/src/t150_arrival.test.ts` AC3.2 dead knobs | **assertion failure** — `spread_scale` / `sensor_sigma` / `transit_temp_bias_c` in web, unwired in `session.rs` |
| AC3.3 | `test_t150_arrival_model.py::test_ac3_3_arrival_summary_includes_f_zero_atom` | **skipped** (`_core` not built) |
| AC3.4 | `web/src/t150_arrival.test.ts` AC3.4 mock deletion + grep guard | **assertion failure** — mock PDF helpers and `arrivalPrior.ts` import from `mock/generate` |
| AC3.5 | `web/src/t150_arrival.test.ts` AC3.5 live_lots wire | **assertion failure** — no `f_spread` / `unit_f` on wire types |
| AC3.6 | `test_t150_arrival_model.py::test_ac3_6_recalibration_artifacts_regenerated` | **assertion failure** — `.t150_physics_epoch` marker and VOI CRN fixture dir absent (notebooks exist) |
| AC3.7 | `test_t150_arrival_model.py::test_ac3_7_changelog_plain_english_entry` | **assertion failure** — no T-150 changelog themes (`corridor`, `upper bound`, …) |
| AC3.8 | — | **Not covered by qa tests** — verifier owns full CI gate per `.cursor/rules/verify-ci-parity.mdc` |

## Not covered by tests

| Criterion | Reason | Verify by |
|-----------|--------|-----------|
| AC1.7 (numeric no-regression) | Property is “no edited numeric expectation in diff”; AC1.7 inertness test passes as baseline | Implementer + reviewer `git diff`; verifier full suite on phase-1-only commit |
| AC3.8 | Role gate: verifier only | `ruff`, `mypy`, full `pytest` cov, `cargo test -p voi_core` on Python 3.11 |

## Guard supersession

No existing guard/closeout tests were weakened. T-140 (`t140_arrival_gamma.rs`) and T-141 tests remain; T-150 supersession lands in phase 2 when `shipments.rs` / `unit_pf.rs` helpers are removed (AC2.15).

## Implementer notes

1. **Do not assert uniform 14× correction** across rungs. Pack-date / temperature branches were ~14× too cheap; P0/P1 default nets ~2.24× via `f_to_age` + `k·θ` division (`day_step.rs:270-276`). Per-branch tests only.
2. **Keep AC2.3 and AC2.4 separate commits/tests** — AC2.3 uses pre-recalibration (k=2, θ=0.08) for spread; AC2.4 pins `gamma_scale = 1/28`.
3. **AC1.7 passes today** — do not break the production path that sets `delivery_lambda` + `delivery_f` when removing `age_at_receipt`.
4. **PyO3 tests skip until `_core` built** — re-run `test_ac2_17`, `test_ac3_1`, `test_ac3_3` after maturin build.
5. **Phase 3 marker** — create `data/abdella/.t150_physics_epoch` when α table, VOI CRN goldens, and notebooks 13/14 are regenerated for the new physics epoch.
