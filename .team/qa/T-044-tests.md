## Coverage of acceptance criteria

- Shared `MF_MAX_SWEEPS = 5` used by age_likelihood default and production P1 path → `tests/test_audit_t044_mf_stubs_hygiene.py::test_mf_max_sweeps_constant_is_five`, `::test_age_likelihood_mean_field_default_uses_mf_max_sweeps`, `::test_backends_p1_path_no_hardcoded_max_sweeps_two`, `::test_production_p1_invokes_mean_field_with_max_sweeps_five` — currently failing: only private `_MF_MAX_SWEEPS`; backends hard-code `max_sweeps=2` (spy sees `[2, …]`)
- `SlidingWindowBackend` / `FullJointBackend` non-citeable stubs (docstring + `is_stub`) → `::test_sliding_window_backend_is_marked_non_citeable_stub`, `::test_full_joint_backend_is_marked_non_citeable_stub` — currently failing: no stub docstring / marker
- `MeanFieldBackend` not a stub → `::test_mean_field_backend_is_not_marked_stub` — currently **passing** (`is_stub` absent)
- `controller/__init__.py` docstring not “Controller stubs (M2).” → `::test_controller_init_docstring_not_stubs_only` — currently failing
- Stale `alpha_tune` “belief=None” comment corrected/removed → `::test_alpha_tune_comment_not_belief_none_stale` — currently failing
- `.team/backlog.md` reflects M2+M3 on main (at/after f4a467f); not pending-merge-as-absent → `::test_backlog_reflects_m2_m3_on_main` — currently failing

## Not covered by tests

- Full ruff/mypy cleanliness for touched modules — verifier / `AGENTS.md` gates after implement
- Optional warn-once on stub backends — not required by ADR 0097 if `is_stub` present

## Notes for implement (T-044)

- Own: `filter/backends.py`, MF constant wiring (`filter/age_likelihood.py`), `controller/__init__.py`, `.team/backlog.md`, α-tune comment only
- Do **not** change case_round / Abdella defaults / VOI α gate (T-042 / T-043)
- CI may slow if P1 always uses 5 sweeps; smoke/tests may pass explicit `max_sweeps=` override where needed
