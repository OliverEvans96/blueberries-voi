## Coverage of acceptance criteria

- RBPF / factory selects `full_joint` when `joint_state_count ≤ MAX_JOINT_FLOATS` → `tests/test_l_fallback.py::test_choose_backend_selects_full_joint_when_within_budget` — currently failing: `choose_backend` not exported
- Same AC (exact budget edge inclusive) → `tests/test_l_fallback.py::test_choose_backend_selects_full_joint_at_exact_budget_edge` — currently failing: `choose_backend` not exported
- Same AC (RBPF surface) → `tests/test_l_fallback.py::test_rbpf_within_budget_uses_full_joint` — currently failing: no `backend_choice` on RBPF
- Over-budget → `sliding_window` → `tests/test_l_fallback.py::test_choose_backend_falls_back_to_sliding_window_when_over_budget` — currently failing: `choose_backend` not exported
- Structured `{K,L,N,joint_floats,backend,reason}` → `tests/test_l_fallback.py::test_fallback_choice_records_structured_reason_fields` — currently failing: `choose_backend` not exported
- RBPF construct over-budget falls back (no MemoryError) → `tests/test_l_fallback.py::test_rbpf_over_budget_falls_back_without_memory_error` — currently failing: still raises MemoryError from `guard_joint_memory`
- RBPF `initialize(L=…)` over-budget preserves L + fallback → `tests/test_l_fallback.py::test_rbpf_initialize_over_budget_preserves_l_and_falls_back` — currently failing: still raises MemoryError
- Never silently truncate L → `tests/test_l_fallback.py::test_choose_backend_never_silently_truncates_l` — currently failing: `choose_backend` not exported
- Dynamic L follows configured max when joint fits → `tests/test_l_fallback.py::test_dynamic_l_follows_configured_max_when_joint_fits` — currently failing: no `backend_choice` (L=4 already kept on construct)
- FIL-12=B not reopened; sliding_window is FIL-13 fallback → `tests/test_l_fallback.py::test_production_default_remains_full_joint_fil12_not_reopened` — currently failing: `choose_backend` not exported (`PRODUCTION_BACKEND` already `full_joint`)
- Frozen `BackendChoice` record → `tests/test_l_fallback.py::test_backend_choice_type_is_frozen_structured_record` — currently failing: `BackendChoice` not exported
- M2.5 experiments note (open-loop + long-dwell + fallback) → `tests/test_l_fallback.py::test_m25_l_remeasure_experiment_note_documents_fallback` — currently failing: `experiments/m25_l_remeasure.md` absent
- Budget lock (prod K/N) → `tests/test_l_fallback.py::test_joint_budget_boundary_l4_fits_l5_trips` — currently **passing**

## Not covered by tests

- Quality gates green / coverage ≥80% — because CI post-implementation bar, verify by `uv run ruff check . && uv run mypy src tests && uv run pytest`
- Sliding-window width default on fallback — because open question in spec, verify by ADR follow-up / bakeoff note
- Fallback sticky vs re-evaluated each day — because open question in spec, verify by ADR follow-up
- Changing `MAX_JOINT_FLOATS` — because out of scope, verify by ADR not by tests
- Multi-rung Stage A (T-016) — because out of scope for T-015
