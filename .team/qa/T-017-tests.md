## Coverage of acceptance criteria

- Stage B per Stage-A-pass rung + 90% CI / ranks + MD/figures under
  `figures/m1.5/` / `experiments/m15_stage_b_*.md`
  → `tests/test_stage_b_oracle.py::test_stage_b_rung_result_schema_fields`
  → `tests/test_stage_b_oracle.py::test_run_m15_stage_b_exported`
  → `tests/test_stage_b_oracle.py::test_run_m15_stage_b_accepts_rungs`
  → `tests/test_stage_b_oracle.py::test_run_m15_stage_b_accepts_shared_root_seed`
  → `tests/test_stage_b_oracle.py::test_run_m15_stage_b_accepts_stage_a_pass_map`
  → `tests/test_stage_b_oracle.py::test_stage_b_rungs_default_or_explicit_six`
  → `tests/test_stage_b_oracle.py::test_stage_b_result_md_path_convention`
  → `tests/test_stage_b_oracle.py::test_figures_readme_maps_stage_b_and_oracle`
  — currently failing: Stage B API / path hooks / README map missing
- A-failing rungs diagnostic-only (or skipped)
  → `tests/test_stage_b_oracle.py::test_diagnostic_only_labeling_for_a_failing_rungs`
  → `tests/test_stage_b_oracle.py::test_run_m15_stage_b_accepts_stage_a_pass_map`
  — currently failing: diagnostic label / Stage A pass map missing
- Coverage band + rank non-U / non-dome pass language
  → `tests/test_stage_b_oracle.py::test_coverage_band_documented_around_90`
    — currently passing (fil11 `STAGE_B_COVERAGE_LO`/`HI`)
  → `tests/test_stage_b_oracle.py::test_rank_histogram_pass_rule_documented`
  — currently failing: rank flatness / narrative hook missing
- B-state age error zero by construction
  → `tests/test_stage_b_oracle.py::test_b_state_age_error_zero_by_construction`
  — currently failing: B-state harness / OracleBelief missing
- Shared-CRN F2 ≪ P1 vs B-state gap table; B-clair out
  → `tests/test_stage_b_oracle.py::test_oracle_gap_row_schema_fields`
  → `tests/test_stage_b_oracle.py::test_run_m15_oracle_ladder_exported`
  → `tests/test_stage_b_oracle.py::test_run_m15_oracle_ladder_shared_root_seed_and_compare_default`
  → `tests/test_stage_b_oracle.py::test_oracle_gap_table_f2_much_less_than_p1_vs_b_state`
  → `tests/test_stage_b_oracle.py::test_oracle_gap_md_path_convention`
  → `tests/test_stage_b_oracle.py::test_b_clair_not_implemented`
  — gap API failing; B-clair absence currently passing
- No CTL / VOI
  → `tests/test_stage_b_oracle.py::test_no_voi_or_ctl_in_stage_b_oracle_surface`
  — currently failing: m15 / stage_b / oracle surface missing
- Empty / unknown rung / empty compare / B-clair in compare
  → `tests/test_stage_b_oracle.py::test_stage_b_empty_rungs_rejected`
  → `tests/test_stage_b_oracle.py::test_stage_b_unknown_rung_rejected`
  → `tests/test_stage_b_oracle.py::test_oracle_ladder_empty_compare_rejected`
  → `tests/test_stage_b_oracle.py::test_oracle_ladder_rejects_b_clair_in_compare`
  — currently failing: runners missing

## Not covered by tests

- Quality gates green / coverage ≥80% — because CI post-implementation bar,
  verify by `uv run ruff check . && uv run mypy src tests && uv run pytest`
- Full expensive Stage B / oracle episode grids / numeric MD table — because
  unit suite must stay cheap; verify by deliberate experiment →
  `experiments/m15_stage_b_*.md`
- Coverage band width and χ² vs visual rank rule — because open questions in
  spec
- B-state mutate-cloud vs `OracleBelief` — because open question in spec
- Stage C / M1.5 close-out — T-012 / T-018; LL/mask changes — out of scope
