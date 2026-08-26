# T-163 — RED criterion → test map (qa)

Recorded on `team/T-163/architect`. Maps spec ACs to failing tests qa must land **before**
implement. Authority: `.team/specs/T-163.md` ← v2 plan §6 checklist + multilot §Verification +
handoff verification targets.

**Stage gate:** prove Stage 1 RED tests before Stage 2 qa shards merge; Stage 2 before Stage 3.

---

## Stage 1 — Transit generative v2

| AC | Test file / symbol | RED mode |
| --- | --- | --- |
| S1.1 | `crates/voi_core/tests/t163_v2_generative.rs::abdella_marginal_d_matches_pooled_gamma` | assertion — MC KS/moment vs `d_min+Gamma(a,b)` |
| S1.2 | `t163_v2_generative.rs::var_log_d_matches_abdella` | assertion — `Var(log d)` not ≈ 0.205 under old fixed legs |
| S1.3 | `t163_v2_calibration.rs::clean_chain_phi_bar_moments` + `tests/test_t163_calibration.py::test_clean_chain_phi_bar_moments` | assertion — mean/SD `φ̄` outside tolerance at `ρ=0` |
| S1.4 | `t163_v2_generative.rs::rho_zero_trace_has_hourly_ou_variation` | assertion — trace temps not constant within stage |
| S1.5 | `t151_cold_chain_breaks.rs::trace_shows_break_pulses_within_duration` (keep) + `break_exposure_is_exactly_additive` (keep) | may pass on partial impl; additive must stay |
| S1.6 | `t151_cold_chain_breaks.rs::trace_integrates_back_to_reported_lambda` (update seeds/tol for v2) | assertion after v2 path rewrite |
| S1.7 | `t163_v2_filter_coherence.rs::generative_duration_law_matches_filter` | assertion — MC `Λ\|d` vs `Duration(d)` drift |
| S1.8 | `t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae` + `ac2_11a_f3_law_matches_generative_mean` | assertion — ordering or ratio under v2 artifact |
| S1.9 | `t151_cold_chain_breaks.rs::artifact_drops_truncated_normal_fields` (extend for `sigma_hour`, modes) + `t163_v2_artifact.rs::artifact_has_v2_thermal_fields` | assertion — missing v2 fields |
| S1.10 | manual / verify note — `bench_day_timing` recorded in `.team/qa/T-163.md` | not a unit test; verify measures |
| S1.11 | `t163_v2_artifact.rs::session_default_unified_corridor` or web control test | assertion — haul chips still first-class |
| S1.12 | `tests/test_t163_calibration.py::test_default_rho_variance_decomposition_design` | assertion — script missing design share output |
| S1.13 | (design lock) covered by S1.5 additive + S1.14 doc test below | — |
| S1.14 | `t163_v2_generative.rs::breaks_clamped_inside_calendar_duration` | assertion — trace duration ≠ `d` when breaks present |
| S1.15 | `t151_cold_chain_breaks.rs::mixture_law_mean_averages_but_variance_exceeds` + `single_component_mixture_is_identity` (keep) | may pass; keep as regression |
| S1.16 | **Supersede** `t151::zero_break_rate_makes_exposure_a_function_of_duration_only` → delete; **replace** `break_free_trip_has_deterministic_exposure` with `t163_v2_generative.rs::rho_zero_exposure_varies_across_draws` | old tests fail or deleted in qa pass |

### Stage 1 — qa shard files

| Shard | New/updated tests | QA map file |
| --- | --- | --- |
| `v2-artifact` | `t163_v2_artifact.rs`, `test_t163_arrival_fit.py` | `.team/qa/T-163-v2-artifact-tests.md` |
| `v2-generative` | `t163_v2_generative.rs`, `t151_cold_chain_breaks.rs` (supersession) | `.team/qa/T-163-v2-generative-tests.md` |
| `v2-filter` | `t163_v2_filter_coherence.rs` | `.team/qa/T-163-v2-filter-tests.md` |
| `v2-guards` | `t163_v2_calibration.rs`, `t150_phase2` ac2_11a, `test_t163_calibration.py` | `.team/qa/T-163-v2-guards-tests.md` |

### Stage 1 — focused RED commands

```bash
cargo test -p voi_core --test t163_v2_generative --test t163_v2_filter_coherence \
  --test t163_v2_artifact --test t163_v2_calibration --test t151_cold_chain_breaks --no-run
cargo test -p voi_core --test t150_phase2_arrival_model ac2_11a -- --nocapture
uv run pytest tests/test_t163_arrival_fit.py tests/test_t163_calibration.py -v --no-cov
```

---

## Stage 2 — Multi-lot (L = 3)

| AC | Test file / symbol | RED mode |
| --- | --- | --- |
| S2.1 | `t163_multilot.rs::delivery_mints_three_lot_ids` | assertion — `arrival_lot_ids.len() != 3` |
| S2.2 | `t163_multilot.rs::lot_exposure_is_upstream_plus_shared` | assertion — `Λ_ℓ` decomposition |
| S2.3 | `t_events_temp_trace.rs` (update) + `t163_multilot.rs::per_lot_traces_spliced` | assertion — single trace or wrong splice |
| S2.4 | `t163_multilot.rs::delivery_quantity_split_not_multiplied` | assertion — total units inflated |
| S2.5 | `unit_pf_ac.rs` (GSIN segment count) + `t163_multilot.rs::gsin_three_segments_per_delivery` | assertion — one segment / wrong law |
| S2.6 | `t163_multilot.rs::upc_merged_cohort_uses_mixture_law` + `t151::mixture_law_*` | assertion — UPC not mixing laws |
| S2.7 | `t163_multilot.rs::resolve_arrival_f_law_per_lot` | assertion — per-delivery law only |
| S2.8 | `t163_multilot.rs::filter_obs_carries_per_lot_pack_dates_and_traces` | assertion — missing per-lot fields / extra mask |
| S2.9 | `unit_pf_ac.rs` (existing loops) — no new test if green | regression only |
| S2.10 | `cargo test -p voi_core -p voi_wasm` full kernel suite | compile/assertion failures in listed tests |

### Stage 2 — qa shard

| Shard | Tests | QA map file |
| --- | --- | --- |
| `multilot` | `t163_multilot.rs`, `t_events_temp_trace.rs`, `unit_pf_ac.rs` | `.team/qa/T-163-multilot-tests.md` |

---

## Stage 3 — Mirrors and guards

| AC | Test file / symbol | RED mode |
| --- | --- | --- |
| S3.1 | `t150_arrival_wire_filter_parity.rs::t150_wire_filter_parity_guard` | assertion — wire ≠ filter on v2 laws |
| S3.2 | `tests/test_rust_parity.py` | assertion — Python `FilterObs` shape drift |
| S3.3 | `tests/test_t128_obs_channels.py` + TS type tests if added | assertion — mask/channel shape |
| S3.4 | `tests/test_studio_release_version.py` | assertion — version not bumped vs merge-base |
| S3.5 | `tests/test_studio_release_version.py` (same) | assertion |
| S3.6 | `tests/test_docs_code_refs.py` | assertion — stale `arrival.rs`/`shipments.rs` line refs |
| S3.7 | `tests/test_rust_parity.py`, `tests/test_simulator_belief_wire.py` | assertion |
| S3.8 | `t150_arrival_wire_filter_parity.rs::t150_wire_filter_parity_guard` | assertion |
| S3.9 | `tests/test_t163_arrival_fit.py::test_fit_script_writes_v2_schema` | assertion — script still emits `mu_T` |

### Stage 3 — qa shard

| Shard | Tests | QA map file |
| --- | --- | --- |
| `mirrors` | wire parity, python parity, docs refs, release version | `.team/qa/T-163-mirrors-tests.md` |

---

## Withdrawn / superseded guards (qa must not reintroduce)

| Withdrawn | Replacement | Source |
| --- | --- | --- |
| "98.4% duration share at `ρ→0`" | `Var(log d) ≈ 0.205` + clean-chain `φ̄` moments + coherence | v2 §3.4; handoff open issue |
| Deterministic `d·φ_set` at `ρ=0` | modes + OU scatter | v2 §1.3–§1.4; S1.16 |
| `short_haul` / `long_haul` first-class UX | unified `abdella_all` | v2 §1.2 |
| `delivery_history_by_lot` mask | structural fork via `code_type` | multilot §3 |

---

## Primary correctness gate (all stages)

`crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae` —
**never relax**. Handoff + v2 §3.4.5.
