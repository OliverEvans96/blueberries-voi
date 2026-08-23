# T-150 — RED criterion → test map (qa)

Recorded on `team/T-150/qa-r3` (2026-08-22, correction round 3 — AC2.11a restatement).

## Commands run (qa-r3 — AC2.11a only)

```bash
# Rust — restated AC2.11a tests (debug, CI profile)
cargo test -p voi_core --test t150_phase2_arrival_model ac2_11a -- --nocapture
# → ac2_11a_f3_law_matches_generative_mean: ok (~8s)
# → ac2_11a_empirical_ladder_tracking_mae: ok (~461s total for ac2_11a filter)
# → ac2_11a_n_scaling_diagnostic: ignored (one-off)

# One-off n-scaling diagnostic (release, recorded below — not CI)
cargo test -p voi_core --release --test t150_phase2_arrival_model ac2_11a_n_scaling -- --ignored --nocapture
```

### AC2.11a — measured table (corrected estimator, seed `150_211`, low-demand fixture)

Standing test (`n = 64`, 20 deliveries, 80-day horizon):

| Quantity | Value |
| --- | --- |
| `MAE(P0)` | 0.1404 |
| `MAE(F2)` | 0.0368 |
| `MAE(F3)` | 0.0153 |
| `floor` | 0.0135 |
| `MAE(F3) / floor` | 1.13 |
| `MAE(P0) / MAE(F2)` | 3.81 |
| implied signal ratio `√(MAE(P0)² − MAE(F3)²) / √(MAE(F2)² − MAE(F3)²)` | 4.17 |

Pre-r3 fixture at `n = 8` (old estimator — `mean_f`, re-draw, 8-unit lots): ordering held but **`MAE(P0)/MAE(F2) = 2.63`** (required 3.0).

Corrected estimator at `n = 8` (mask replay, atom-inclusive, same seed — diagnostic only): **`MAE(P0)/MAE(F2) = 2.83`** — still below 3.0; effect not resolved at 8 units (expected per spec §r3).

### AC2.11a — n-scaling diagnostic (`ac2_11a_n_scaling_diagnostic`, release, one-off)

| `n` | deliveries | `MAE(F3)` | `floor` |
| --- | --- | --- | --- |
| 8 | 15 | 0.0496 | 0.0324 |
| 64 | 20 | 0.0153 | 0.0135 |
| 256 | 20 | 0.0083 | 0.0068 |

**Verdict:** `MAE(F3)` falls approximately as `1/√n` (8→64: ×0.31 vs `1/√8` predict ×0.35; 64→256: ×0.54 vs ×0.50). **F3 is at its Bayes floor, not biased** — r3 finding confirmed. No Phase 2 reopen.

### AC2.11a — runtime (debug build, CI profile)

| Test | Wall-clock |
| --- | --- |
| `ac2_11a_empirical_ladder_tracking_mae` | ~632s (single test), ~453s in paired `ac2_11a` run |
| `ac2_11a_f3_law_matches_generative_mean` | ~8s |
| **Profile:** session `step` + filter (80 episode days, 64-unit arrivals) dominates; removing `draw_truth_delivery` re-draw and mask-replay obs reads are comparatively cheap. No `#[ignore]` on the standing test — ~7–10 min in debug is within CI practicality vs the pre-r3 8-unit fixture (>1 h reported in debug elsewhere). |

**Fixture choices for runnable gate:** standing test uses **only** the `n = 64` case (20 deliveries, order every 4 days); n-scaling sweep is `#[ignore]` with numbers recorded here; low-demand profile (`scale_target_mu = 0.01`) keeps lots on `live_lots` after delivery under high unit counts (default demand otherwise sells out same-day and hides birth lots from the wire).

---

Recorded after focused RED runs on `team/T-150/qa-r2-implement` (2026-08-22 correction round).

## Commands run (RED evidence — correction round)

```bash
# Rust — new / corrected Phase 2 tests only
cargo test -p voi_core --test t150_phase2_arrival_model ac2_11a_empirical -- --nocapture
cargo test -p voi_core --test t150_phase2_arrival_model ac2_19_ -- --nocapture
cargo test -p voi_core --test t150_phase2_arrival_model ac2_20_f3 -- --nocapture
# → ac2_11a: FAILED | ac2_19: 5 failed, 0 passed | ac2_20: 2 failed

# Python 3.11 — AC2.18 only
uv sync --all-extras --python 3.11
.venv/bin/python -m pytest tests/test_t150_arrival_model.py::test_ac2_18_arrival_artifact_anchored_to_abdella_shipments -v
# → FAILED (sigma_T ratio 6.83× observed)
```

### Excerpt — AC2.18 (Python, committed artifact)

```
FAILED test_ac2_18_arrival_artifact_anchored_to_abdella_shipments
AssertionError: RED: sigma_T ratio 6.83 must be in [0.5, 2.0]
  (artifact=3.6, observed sd(T_i)=0.527)
```

### Excerpt — AC2.11a (Rust)

```
RED: ladder MAE must order F3 < F2 < P0 strictly; got F3=0.3381 F2=0.1059 P0=0.3267
```

### Excerpt — AC2.19 / AC2.20 (Rust, representative)

```
ac2_19_quadrature_d_and_tbar_independent_product: |r|=0.9325 (shared quadrature index)
ac2_19_quadrature_integrates_modeled_densities: quad mean d 4.700 vs shifted-gamma 2.800
ac2_19_sigma_pos_in_filter_law: sd unchanged when sigma_pos 0.02→0.20 (0.2419 vs 0.2419)
ac2_19_atom_single_count_and_unconditional_moments: filter atom 0.0962 vs analytic 0.0006
ac2_19_prior_single_corridor_no_mix_weight: mix_weight still on abdella_all
ac2_20_f3_laws_differ_when_duration_differs_at_same_phi_bar: means 0.3894 vs 0.3894 (phi_bar-only cache)
ac2_20_f3_law_sufficient_in_lambda_not_phi_bar: equal Λ means 0.4315 vs 0.2341 (must match)
```

## Guard supersession (correction round)

**Withdrawn AC2.10** — removed in this commit before implementer touches the artifact:

| Removed | Location |
|---------|----------|
| `ac2_10_monotone_ladder_variance` | `crates/voi_core/tests/t150_phase2_arrival_model.rs` |
| `monotone_ladder_variance_strict` | `crates/voi_core/src/arrival.rs` (`#[cfg(test)]`) |
| AC2.10 row | this map (placeholder below) |
| `ArrivalModel::variance_f_given_phi_bar` | `crates/voi_core/src/arrival.rs` — **deleted** (only callers were the withdrawn tests) |

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

### Phase 2 (20 criteria — AC2.10 withdrawn, not renumbered)

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
| *(AC2.10 withdrawn)* | *Monotone `Var(f\|φ̄) < Var(f\|d) < Var(f)` guard retired per ADR 0144 Correction 1 — tests deleted in this round* | *n/a* |
| AC2.11 | `t150_phase2_arrival_model.rs::ac2_11_f2_marginals_differ_from_p0`, `ac2_11_caught_up_f2_not_collapsed_to_p0`, `ac2_11_p0_p1_posteriors_differ` | **assertion failure** (F2/P0/catch-up); P0≠P1 **passes** today |
| AC2.11a | `t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`, `ac2_11a_f3_law_matches_generative_mean` | **GREEN at `n ≥ 64`** with corrected estimator on `team/T-150/integrate` — ordering strict, `MAE(P0)/MAE(F2) = 3.81`, `MAE(F3)/floor = 1.13`; **RED at `n = 8`** on ratio only (`2.83 < 3.0`) documents noise floor (see measured table above). Pre-r3 test failed ratio `2.63` at `n = 8` with wrong estimator (`mean_f`, re-draw). |
| AC2.11a n-scaling | `t150_phase2_arrival_model.rs::ac2_11a_n_scaling_diagnostic` (`#[ignore]`) | **diagnostic only** — F3 scales as `1/√n`; not CI gate |
| AC2.12 | `t150_phase2_arrival_model.rs::ac2_12_within_lot_arrival_f_spread` | **assertion failure** — truth path still uses `delivery_birth_f`; `live_lots` lacks spread fields |
| AC2.13 | `t150_phase2_arrival_model.rs::ac2_13_filter_obs_no_freshness_valued_arrival` | **assertion failure** — `FilterObs.age_at_receipt` / `f_at_receipt` still present |
| AC2.14 | `t150_phase2_arrival_model.rs::ac2_14_truth_path_f_native_arrival` | **assertion failure** — `f_to_age` round trip and `birth_f_units_gamma` on truth path |
| AC2.15 | `t150_phase2_arrival_model.rs::ac2_15_filter_path_and_shipments_cleanup` | **assertion failure** — `resolve_arrival_lambda` and superseded `shipments.rs` helpers remain |
| AC2.16 | `t150_phase2_arrival_model.rs::ac2_16_lambda_floor_finite_cdf` | **assertion failure** — `arrival.rs` floor not implemented (analytic `gamma_p`/`gamma_q` baseline passes) |
| AC2.17 | `t150_phase2_arrival_model.rs::ac2_17_rust_embed_parses_committed_artifact` + `test_t150_arrival_model.py::test_ac2_17_python_rust_arrival_artifact_parity` | **assertion failure** / **skipped** — no `pub mod arrival`; PyO3 parity blocked until `_core` built |
| AC2.18 | `tests/test_t150_arrival_model.py::test_ac2_18_arrival_artifact_anchored_to_abdella_shipments` | **assertion failure** — `sigma_T=3.6` is 6.8× observed Arrhenius sd (`0.527`); duration share under artifact laws ≪ 0.90 with `delay_scale=0.30` |
| AC2.19 | `t150_phase2_arrival_model.rs::ac2_19_quadrature_d_and_tbar_independent_product`, `ac2_19_quadrature_integrates_modeled_densities`, `ac2_19_sigma_pos_in_filter_law`, `ac2_19_atom_single_count_and_unconditional_moments`, `ac2_19_prior_single_corridor_no_mix_weight` | **assertion failure** — all five `build_marginal_cdf` defects present (see excerpts above) |
| AC2.20 | `t150_phase2_arrival_model.rs::ac2_20_f3_laws_differ_when_duration_differs_at_same_phi_bar`, `ac2_20_f3_law_sufficient_in_lambda_not_phi_bar` | **assertion failure** — F3 cache keyed on `φ̄` only: same `φ̄` ignores duration; equal `Λ` with different `φ̄` yields different laws |

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

## Implementer notes

1. **Do not assert uniform 14× correction** across rungs. Pack-date / temperature branches were ~14× too cheap; P0/P1 default nets ~2.24× via `f_to_age` + `k·θ` division (`day_step.rs:270-276`). Per-branch tests only.
2. **Keep AC2.3 and AC2.4 separate commits/tests** — AC2.3 uses pre-recalibration (k=2, θ=0.08) for spread; AC2.4 pins `gamma_scale = 1/28`.
3. **AC1.7 passes today** — do not break the production path that sets `delivery_lambda` + `delivery_f` when removing `age_at_receipt`.
4. **PyO3 tests skip until `_core` built** — re-run `test_ac2_17`, `test_ac3_1`, `test_ac3_3` after maturin build.
5. **Phase 3 marker** — create `data/abdella/.t150_physics_epoch` when α table, VOI CRN goldens, and notebooks 13/14 are regenerated for the new physics epoch.
6. **Correction round priorities** — land target artifact (`sigma_T=0.4`, `delay_scale=1.0`, delete `mix_weight`) per AC2.18; rewrite `build_marginal_cdf` as a product rule over modeled densities with `ψ_pos`; F3 cache keyed on exact `Λ` (`ArrivalCondition::Exposure`), not `exposure/duration`; delete `resolve_arrival_f_law_phi_bar` division path.
7. **AC2.11a (r3)** — do not add `sd(f|F3) < sd(f|F2)` at tight tolerance; tracking MAE separates rungs, residual spread does not (`φ̄` ≈ 1.6% of `Var(log Λ)`). **Truth target must be atom-inclusive:** `Σ(f_values)/DayDelta.arrivals` with zeros padded for the `f = 0` shortfall — not `live_lots.mean_f` (which is `E[f|f>0]`). **One trajectory, mask replay:** observations from `events_value(0)` under F2/F3; never re-draw via `draw_truth_delivery`. **Lot size ≥ 64 units** so the noise floor (`≈0.013`) sits below the F2→P0 signal (`≈0.025`); at `n = 8` the 3× ratio gate is unreachable even with a correct model. Standing test is `n = 64` only; n-scaling diagnostic is `#[ignore]`.
