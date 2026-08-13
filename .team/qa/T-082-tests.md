# T-082 RED map — DemandModel + draw_demand(day=) (ADR 0113/0112/0113)

## Coverage of acceptance criteria

- `draw_demand(rng, params, *, day: int | None = None)` public signature; day+profile
  → μ(day); day None / no profile → prior `demand_mu` compat  
  → `tests/test_t082_demand_model.py::test_draw_demand_signature_is_keyword_only_day_optional`
  — currently failing: `day` absent from signature (`rng`, `params` only)  
  → `…::test_draw_demand_day_none_without_profile_matches_prior_demand_mu` — currently
  failing: same (blocked on `day=` before mean assert)  
  → `…::test_draw_demand_with_day_and_profile_uses_profile_mu` — currently failing:
  `load_demand_profile` not importable from `model` / `model.demand*`

- `ModelParams` (or companion) carries loaded profile; loader JSON-only (no HF)  
  → `…::test_load_demand_profile_reads_committed_json_without_freshnet_extra` —
  currently failing: missing `load_demand_profile` / `DemandProfile`  
  → `…::test_load_demand_profile_source_has_no_hf_imports` — currently failing:
  same (symbol required so guard is not vacuous)

- Loading committed `data/freshnet/demand_profile.json` succeeds without `[freshnet]`  
  → covered by `test_load_demand_profile_reads_committed_json_without_freshnet_extra`
  (stdlib JSON path; asserts no HF modules loaded)

- `day_step` uses day-indexed demand when day/profile supplied (via `draw_demand` or
  equivalent); CRN can pass episode day  
  → `…::test_day_step_uses_day_indexed_demand_when_day_and_profile_supplied` —
  currently failing: missing `load_demand_profile` (will assert μ(day) mean once
  wired; allows `day_step(day=)` **or** `draw_demand(..., day=)` + `demand=`)

- Two different weekdays with distinct profile means → different μ  
  → `…::test_distinct_weekdays_with_distinct_profile_means_differ` — currently
  failing: missing profile loader / μ accessor (Thu vs Sun vs committed JSON)

- Package import graph still excludes `datasets` / HF  
  → `…::test_package_import_graph_excludes_datasets_and_hf` — **passing** (guard)  
  → `…::test_importing_model_does_not_load_datasets_or_huggingface` — **passing**

- A2 shim tests remain collectable/green where applicable  
  → `…::test_a2_shim_positional_draw_demand_still_callable` — **passing**  
  → `…::test_a2_shim_draw_demand_day_default_preserves_constant_mu_nb` — **passing**  
  → `tests/test_model.py::test_demand_negative_binomial_defaults` — **passing**
  (pre-CAL / A2 call path without `day=`)

## Proven RED

```text
uv sync --all-extras --python 3.11
uv run --python 3.11 pytest tests/test_t082_demand_model.py \
  tests/test_model.py::test_demand_negative_binomial_defaults --no-cov -v
# 7 failed, 5 passed — failures are missing day= / load_demand_profile /
# DemandProfile (not import typos or collection errors)
```

## Not covered by tests

- Exact `ModelParams` field name (`demand_profile` vs companion factory) — tests
  accept several field names / `with_demand_profile`.
- Whether `day_step` gains `day=` vs callers pre-drawing — both paths accepted once
  day-indexed μ is observable.
- Exact μ accessor name (`profile.mu` / `demand_mu_for_day` / …) — several accepted.
- CRN multi-scenario identity regression (T-084) beyond day wiring.
- Controller protection convolution upgrade (T-084).
- `ruff` / `mypy` on touched paths — implement / verify role gates.
