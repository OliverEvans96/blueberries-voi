# T-069 QA — ShelfBelief arrival-prior exports, Stage A re-gate, changelog (RED map)

DATE: 2026-08-13
STATUS: RED — belief factory/docs still claim MF posteriors (ADR 0092 wording);
Stage A `experiments/` / fil11 harness lack F2a/F2-prior + P0/P1/F1 honesty
language; changelog missing T-069 RB-age rationale. Failures are
`AssertionError` on missing behaviour/docs, not import/typo errors.

Runtime arrival export + ENG-01 flatten already match filter-carried birth
priors after T-068 (those checks are green); implement must update docs,
changelog, and factory wording so the RED assertions pass.

## Spec under test

`.team/specs/T-069.md` + ADR 0106 (cascade from ADR 0105)

## RED confirmation

```bash
uv sync --extra dev
uv run pytest \
  tests/test_belief_arrival_priors.py \
  tests/test_belief.py::test_shelf_belief_from_rbpf_matches_arrival_age_rows_shape_and_values \
  -v --tb=short --no-cov
```

Result: **5 failed, 6 passed** on the focused set above.

## Coverage of acceptance criteria

- `shelf_belief_from_rbpf` exports `age_marginals` derived from arrival belief
  (not MF posteriors); nested `(L,K)` unchanged
  → `tests/test_belief_arrival_priors.py::test_shelf_belief_from_rbpf_docs_state_arrival_prior_not_mf`
  — currently failing: factory/module still describe MF posteriors / ADR 0092
  → `tests/test_belief_arrival_priors.py::test_shelf_belief_from_rbpf_f2_dirac_matches_birth_prior_shape`
  — currently **passing** (T-068 age_post already carries F2 Dirac birth prior)
  → `tests/test_belief_arrival_priors.py::test_shelf_belief_from_rbpf_ages_differ_from_mean_field_update`
  — currently **passing** (export ≠ diagnostic `mean_field_update`)
  → `tests/test_belief_arrival_priors.py::test_shelf_belief_from_rbpf_f2a_path_matches_delivery_birth_prior`
  — currently **passing** (F2a pack-date birth prior path)
  → `tests/test_belief.py::test_shelf_belief_from_rbpf_matches_arrival_age_rows_shape_and_values`
  — currently failing: supersedes MF-named guard; docstring still claims MF
    (shape/value match vs `age_posterior` already holds)

- ENG-01 flatten / Snapshot–DayDelta path remains wire-compatible (flat `L·K`)
  → `tests/test_belief_arrival_priors.py::test_flatten_shelf_belief_from_rbpf_is_wire_compatible_l_times_k`
  — currently **passing** (field names + length `L*K`)
  → `tests/test_belief_arrival_priors.py::test_flatten_shelf_belief_row_major_matches_nested_arrival_rows`
  — currently **passing** (row-major flatten preserves F2 Dirac slice)

- Stage A–style docs/harness under `experiments/` state F2a/F2 age info from
  **priors**; P0/P1/F1 do **not** claim in-store age learning as a production gate
  → `tests/test_belief_arrival_priors.py::test_stage_a_docs_state_f2_age_information_comes_from_priors`
  — currently failing: Stage A docs/harness omit F2a/F2 prior-honesty phrasing
  → `tests/test_belief_arrival_priors.py::test_stage_a_docs_p0_p1_f1_do_not_claim_instore_age_learning_gate`
  — currently failing: no P0/P1/F1 + “not an in-store age-learning gate” language

- `.team/changelog.md` plain-English entry: RB / in-store age marginalisation
  removed because **in-store age learning was dropped** (T-069)
  → `tests/test_belief_arrival_priors.py::test_changelog_states_rb_age_removed_because_instore_learning_dropped`
  — currently failing: no T-069 changelog entry yet

- Automated tests cover arrival-derived ages (F2 Dirac / F2a) + flatten `L·K`
  → covered by the arrival + flatten tests above (this file is the AC lock)

- Quality gates: qa RED `--no-cov` (this tip); implement green; reviewer /
  verifier later
  → process — verify by role handoff

## Not covered by tests

- Full re-run of expensive FIL-11 Stage A numeric grids / figure regeneration —
  because unit tests lock honesty language and belief wire semantics; numeric
  Stage A re-gate is implement/harness work verified by reading updated MD /
  optional smoke, not by CI episode sweeps.
- Citeable calibrated VOI science claims — out of scope per spec.
- Restoring in-store age LL / rewriting filter weight core — T-068 / out of scope.

## Guard supersession

- Renamed/replaced
  `tests/test_belief.py::test_shelf_belief_from_rbpf_matches_mf_age_posterior_shape_and_values`
  with
  `test_shelf_belief_from_rbpf_matches_arrival_age_rows_shape_and_values`
  (ADR 0106 supersedes ADR 0092 MF reading of `age_marginals`).
