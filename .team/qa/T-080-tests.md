# T-080 RED map — Fit demand_profile.json (ADR 0115)

## Coverage of acceptance criteria

- Fit script under `scripts/` requiring `[freshnet]` produces committed
  `data/freshnet/demand_profile.json` (git-sized, not raw HF dump)  
  → `tests/test_t080_freshnet_demand_profile.py::test_fit_freshnet_demand_script_exists_under_scripts`
  — currently failing: no `fit_freshnet_demand.py` (ingest `fetch_freshnet.py` excluded)  
  → `…::test_fit_script_documents_freshnet_extra_requirement` — currently failing: same  
  → `…::test_fit_script_exits_nonzero_when_freshnet_deps_missing` — currently failing: same  
  → `…::test_demand_profile_json_exists_and_is_git_sized` — currently failing:
  `demand_profile.json` absent

- Profile encodes DOW × week-index (or month) mean structure + dispersion / scale
  metadata  
  → `…::test_demand_profile_encodes_dow_by_week_structure` — currently failing: profile
  missing (will assert dow/week factors or DOW×week table once present)  
  → `…::test_demand_profile_records_demand_vm` — currently failing: profile missing

- Operational mean / `scale_target_mu` ≈ **30** within documented absolute **±1**  
  → `…::test_demand_profile_scale_target_mu_near_30` — currently failing: profile missing  
  → `…::test_fit_report_documents_scale_tolerance_matching_tests` — currently failing:
  fit report missing (must document ±1)

- Fit report records SKU IDs, censoring rule, V/M choice, Mar–Jun honesty  
  → `…::test_fit_report_artifact_exists_beside_profile` — currently failing: no
  `fit_report.md` / `.json`  
  → `…::test_fit_report_records_sku_ids_censoring_vm_and_mar_jun_honesty` — currently
  failing: same

- `PROVENANCE.md` updated with final SKU ID list and pointers to profile + fit report  
  → `…::test_provenance_lists_final_sku_ids` — currently failing: still
  `Selected SKU IDs: _TBD`  
  → `…::test_provenance_points_to_profile_and_fit_report` — currently failing: fit
  report absent (`demand_profile.json` string already mentioned as T-080 OOS)

- Profile schema is versioned  
  → `…::test_demand_profile_schema_is_versioned` — currently failing: profile missing

- Pytest does **not** require live HF download; committed JSON is source of truth  
  → `…::test_this_module_does_not_import_huggingface_or_datasets` — **passing**  
  → `…::test_demand_profile_loads_without_network_or_freshnet_extra` — currently failing:
  profile missing (loads via stdlib `json` only once present)

- No HF import from package runtime modules  
  → `…::test_src_package_tree_has_no_hf_imports` — **passing** (guard; implement must
  not regress)

## Proven RED

```text
uv sync --all-extras --python 3.11
uv run --python 3.11 pytest tests/test_t080_freshnet_demand_profile.py --no-cov -v
# 14 failed, 2 passed — failures are missing demand_profile.json / fit report /
# fit script / final SKU list in PROVENANCE (not import typos)
```

## Not covered by tests

- Actual Hugging Face download or running the numerical fit — offline assertions only;
  implement may run fit locally with `[freshnet]`; do not require network in CI.
- Exact JSON key names beyond `schema_version` / `scale_target_mu` / `demand_vm` and
  DOW×week markers — implementer documents boring schema; tests accept equivalent
  factor/table keys.
- Exact V/M numeric choice (refit vs 2.0) — report must record the decision; profile
  must store a positive `demand_vm`.
- `ruff` / `mypy` on touched paths — implement / verify role gates (AGENTS.md).
