# T-052 test map (RED — Slice 2 close-out DoD contracts)

## Coverage of acceptance criteria

- QA notes mark T-049–T-051 DONE / green
  → `tests/test_slice2_closeout.py::test_slice2_ticket_qa_or_verify_green`
  — currently failing: primary QA for T-050/T-051 still STATUS RED; no T-049 qa note;
    no `T-XXX-verify.md` on tip; RED `.team/qa/T-052.md` does not list children green
  → `tests/test_slice2_closeout.py::test_slice2_ticket_verify_pass_artifact_present`
  — currently failing: missing `.team/qa/T-050-verify.md` / `T-051-verify.md`
    (gather from `team/T-050/verify` @ `40c61f5` and `team/T-051/verify`)

- `.team/reviews/` APPROVED for T-050–T-051 (DoD / parent brief)
  → `tests/test_slice2_closeout.py::test_slice2_ticket_review_approved`
  — currently failing: no review artifacts on implement tip (copy from
    `team/T-050/review` / `team/T-051/review`)

- Changelog entry: developers can drive the same simulator engine over a local HTTP API
  for iteration (client voice)
  → `tests/test_slice2_closeout.py::test_changelog_has_slice2_client_voice_entry`
  — currently failing: no Slice-2 / local HTTP API close-out entry yet

- Checklist asserts API responses share Snapshot/DayDelta with Pyodide and do not claim
  production multi-tenant hosting
  → `tests/test_slice2_closeout.py::test_slice2_closeout_contract_checklist`
  — currently failing: no Slice-2 close-out DoD / contract note under `.team/reviews/`
    (RED `.team/qa/T-052.md` is excluded until STATUS flips)

- Plan Slice-2 waves marked complete
  → `tests/test_slice2_closeout.py::test_eng01_plan_slice2_waves_complete`
  — currently failing: status still “Wave 0 architect lock”; ticket-map “T-052 close-out”
    title alone does not count

- No merge to `main` by agents
  → `tests/test_slice2_closeout.py::test_slice2_pending_human_merge_not_merged_by_agents`
  — currently failing: no Slice-2/T-052 “complete pending human merge” lock
    (M2/M3/Slice-1 lines ignored)

- Do not weaken CI gates
  → `tests/test_slice2_closeout.py::test_ci_quality_gates_not_weakened`
  — currently passing (cov-fail-under=80 + mypy strict already locked)

- T-052 spec AC checkboxes marked done at close-out
  → `tests/test_slice2_closeout.py::test_t052_spec_acceptance_criteria_checked`
  — currently failing: all five T-052 AC items still `[ ]`

## Not covered by tests

- Full AGENTS.md toolchain (ruff / mypy / full pytest + coverage ≥80%) — verifier gate;
  verify by running the commands at close-out and recording in `.team/qa/T-052-verify.md`
- Literally proving git history has no agent merge commit to `main` — process / human;
  tests lock the backlog/close-out *claim* that agents did not merge
- Gathering review/verify blobs from parallel role tips — implementer copies files; tests
  only assert presence on the close-out tip
- D3 integration / Slice 3 — out of scope per spec

## Unhappy / boundary notes

- Primary QA may remain historically RED if `T-XXX-verify.md` is PASS (or T-052 PASS lists
  the ticket green/DONE); either path satisfies the “qa notes … green/DONE” AC
- T-049 (Wave-0 docs lock) needs green/DONE qa notes but does not require a separate
  verify artifact on this tip (implement reviews/verify are locked for T-050–T-051)
- Review coverage is by filename subject tokens or Slice-2 / ENG-01 close-out spanning
  T-050–T-051, not incidental mentions in unrelated reviews
- Contract checklist must *assert* Snapshot/DayDelta↔Pyodide parity and negate
  production multi-tenant hosting (checked `[x]` items count)
- Changelog must mention developers / local HTTP API / same simulator engine in client
  voice (not OpenAPI/TestClient-only jargon)
