# T-078 RED map — FreshNet ingest + PROVENANCE (ADR 0115)

## Coverage of acceptance criteria

- Script under `scripts/` (documented) can download/refresh FreshRetailNet-50K via
  optional `[freshnet]`  
  → `tests/test_t078_freshnet_ingest.py::test_freshnet_ingest_script_exists_under_scripts`
  — currently failing: no `fetch_freshnet.py` / `freshnet_ingest.py` (or FreshNet-named
  script) under `scripts/`  
  → `…::test_freshnet_ingest_script_is_documented` — currently failing: same (script
  missing)

- `pyproject.toml` declares optional `[freshnet]` with HF/`datasets`; core / `[browser]`
  do not require them  
  → `…::test_pyproject_declares_freshnet_optional_extra_with_hf_deps` — currently failing:
  `optional-dependencies.freshnet` absent  
  → `…::test_core_and_browser_extras_do_not_require_freshnet_hf_deps` — **passing** (core
  / browser already free of HF markers; implement must not regress)

- `data/freshnet/PROVENANCE.md` records dataset id, CC BY 4.0, access method, download
  date/revision placeholder, SKU selection rule text  
  → `…::test_freshnet_provenance_md_exists` — currently failing: file missing  
  → `…::test_freshnet_provenance_records_dataset_id_license_access_sku_rule` — currently
  failing: PROVENANCE.md missing

- Importing `blueberries_voi` does not import `datasets` / huggingface hub clients  
  → `…::test_package_init_source_has_no_datasets_or_huggingface_imports` — **passing**  
  → `…::test_importing_blueberries_voi_does_not_load_datasets_or_huggingface` — **passing**  
  → `…::test_src_package_tree_has_no_eager_hf_imports` — **passing**  
  (guards already green; implement must keep HF out of the installable package)

- No `demand_profile.json` fit required (fit is T-080)  
  → `…::test_demand_profile_json_not_required_for_t078_ingest` — **passing** (file absent
  is allowed)

- Script exits non-zero with a clear message if `[freshnet]` deps are missing  
  → `…::test_freshnet_script_exits_nonzero_when_freshnet_deps_missing` — currently failing:
  script missing (subprocess + blocked HF env ready once implement lands the script)

- Raw cache path gitignored / documented  
  → `…::test_freshnet_raw_cache_path_documented_and_gitignore_covered` — currently failing:
  PROVENANCE.md missing (will assert documented path ∩ `.gitignore`)

## Proven RED

```text
uv sync --all-extras
uv run pytest tests/test_t078_freshnet_ingest.py --no-cov -v
# 7 failed, 5 passed — failures are missing script / [freshnet] extra / PROVENANCE
```

## Not covered by tests

- Actual Hugging Face download / refresh of multi-GB parquet — offline assertions only;
  verify manually with `[freshnet]` installed outside CI if needed.
- Exact cache directory basename — implementer picks a boring gitignored default and
  documents it; tests only require a documented path covered by `.gitignore`.
- `uv run ruff` / `mypy` on touched paths — implement / verify role gates (AGENTS.md).
