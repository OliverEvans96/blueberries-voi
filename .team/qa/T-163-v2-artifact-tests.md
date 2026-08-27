# T-163 v2-artifact — RED criterion → test map (qa)

Shard: `v2-artifact` on `team/T-163/v2-artifact-implement`. Authority: `.team/specs/T-163.md` S1.9–S1.12.

## Coverage of acceptance criteria

- S1.9 — `crates/voi_core/tests/t163_v2_artifact.rs::artifact_has_v2_thermal_fields` — currently failing: committed `arrival_model.json` lacks `thermal_modes` and `sigma_hour`
- S1.9 — `crates/voi_core/tests/t163_v2_artifact.rs::artifact_drops_truncated_normal_and_carries_v2_break_fields` — currently failing: missing `thermal_modes` / `sigma_hour` (truncated-normal keys already absent)
- S1.9 — `tests/test_t163_arrival_fit.py::test_committed_artifact_has_v2_thermal_fields` — currently failing: same missing v2 thermal fields
- S1.10 — `tests/test_t163_arrival_fit.py::test_fit_script_build_artifact_fits_duration_only` — currently failing: `_build_artifact` still calls `_fit_truncated_normal_t` and emits `mu_T` / `sigma_T` / `temp_floor_c`
- S1.10 — `tests/test_t163_arrival_fit.py::test_fit_script_documents_assumed_thermal_modes_sigma_hour_and_breaks` — currently failing: fit script source has no `thermal_modes` / `sigma_hour` provenance strings
- S1.10 — `tests/test_t163_arrival_fit.py::test_fit_report_documents_assumed_not_fitted_thermal_knobs` — currently failing: `fit_report.md` still documents `mu_T` / `sigma_T`; lacks assumed thermal knob section
- S1.11 — `crates/voi_core/tests/t163_v2_artifact.rs::session_default_unified_corridor` — partially failing: default `arrival_product` is `abdella_all` (passes) but `web/src/controls.ts` still exposes `short_haul` / `long_haul` arrival chips
- S1.12 — `tests/test_t163_arrival_fit.py::test_calibration_note_reports_design_variance_decomposition` — currently failing: `calibration_note.md` lacks Var(log Λ) duration vs break variance share

## Not covered by tests

- S1.12 (spec: per-day `bench_day_timing` ~5.7 ms/day) — verify-only measurement in `.team/qa/T-163.md`, not a unit test in this shard

## Focused RED commands

```bash
cargo test -p voi_core --test t163_v2_artifact --no-run
cargo test -p voi_core --test t163_v2_artifact
uv run pytest tests/test_t163_arrival_fit.py -v --no-cov
```
