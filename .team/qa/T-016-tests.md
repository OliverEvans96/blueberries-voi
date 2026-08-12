## Coverage of acceptance criteria

- Runnable experiment covers rungs **{P0, P1, F1, F1s, F2a, F2}** with shared
  `root_seed` → `tests/test_stage_a_multirung.py::test_run_m15_stage_a_exported`
  → `tests/test_stage_a_multirung.py::test_run_m15_stage_a_default_rungs_cover_six_scenarios`
  → `tests/test_stage_a_multirung.py::test_run_m15_stage_a_accepts_shared_root_seed`
  — currently failing: `run_m15_stage_a` not exported
- Prior vs posterior SD + contracted + tight-control + ≥5% margin +
  cohort-from-birth docs →
  `tests/test_stage_a_multirung.py::test_stage_a_rung_result_schema_fields`
  → `tests/test_stage_a_multirung.py::test_stage_a_multi_result_schema_fields`
  → `tests/test_stage_a_multirung.py::test_run_m15_stage_a_default_contraction_margin`
  → `tests/test_stage_a_multirung.py::test_cohort_from_birth_metric_documented`
  — currently failing: types / margin defaults / metric hook missing
- Result MD + P0/P1 FAIL allowed + higher-rung honesty →
  `tests/test_stage_a_multirung.py::test_p0_p1_fail_allowed_documentation_hook`
  → `tests/test_stage_a_multirung.py::test_higher_rung_expectations_documented`
  → `tests/test_stage_a_multirung.py::test_result_md_convention_and_p0_p1_fail_language`
  — currently failing: narrative / path hooks / MD absent
- Figures under `figures/m1.5/` + README map →
  `tests/test_stage_a_multirung.py::test_figures_readme_maps_stage_a_rungs`
  — currently failing: README lacks Stage A rung mapping
- No VOI dollars; no CTL →
  `tests/test_stage_a_multirung.py::test_no_voi_dollars_or_ctl_in_stage_a_surface`
  — currently failing: `viz.m15` / `viz.stage_a` missing
- Empty / unknown rung / margin boundaries →
  `tests/test_stage_a_multirung.py::test_empty_rungs_rejected`
  → `tests/test_stage_a_multirung.py::test_unknown_rung_rejected`
  → `tests/test_stage_a_multirung.py::test_contraction_margin_boundaries`
  — currently failing: runner missing

## Not covered by tests

- Quality gates green / coverage ≥80% — because CI post-implementation bar,
  verify by `uv run ruff check . && uv run mypy src tests && uv run pytest`
- Full expensive multi-rung Stage A grids / numeric PASS table — because unit
  suite must stay cheap; verify by deliberate experiment →
  `experiments/m15_stage_a_result.md`
- Exact cohort age (birth lot vs shelf) and min scored days/particles — because
  open questions in spec
- Stage B / oracle (T-017); LL/mask changes — out of scope
