# T-058 test map (RED — ENG-01 / Slice 3 close-out DoD contracts)

## Coverage of acceptance criteria

- QA notes mark T-053–T-057 DONE / green
  → `tests/test_eng01_closeout.py::test_slice3_ticket_qa_or_verify_green`
  — currently failing: T-053/T-054 missing qa+verify; T-055–T-057 primary QA still STATUS RED and no `T-XXX-verify.md` on tip
  → `tests/test_eng01_closeout.py::test_slice3_ticket_verify_pass_artifact_present` (T-054–T-057)
  — currently failing: missing `.team/qa/T-054-verify.md` … `T-057-verify.md`
  (gather from `team/T-05X/verify`)

- `.team/reviews/` APPROVED for T-054–T-057 (parent brief / DoD)
  → `tests/test_eng01_closeout.py::test_slice3_ticket_review_approved`
  — currently failing: no review artifacts on implement tip (copy from `team/T-05X/review`)

- Changelog entry (client voice): readers can interact with the live simulator in the
  browser (demo budgets), and developers can iterate via the local API
  → `tests/test_eng01_closeout.py::test_changelog_has_eng01_client_voice_entry`
  — currently failing: no ENG-01 / Slice-3 dual-runtime close-out entry yet

- Close-out checklist asserts non-goals: not full WASM A; not JS-only B as prod; no
  matplotlib/pyarrow in browser; no production-N-in-tab claim; honesty/cadence ⚑ still out
  → `tests/test_eng01_closeout.py::test_eng01_closeout_nongoals_checklist`
  — currently failing: no ENG-01 / Slice-3 close-out DoD / non-goal note under
    `.team/reviews/` (RED `.team/qa/T-058.md` is excluded until STATUS flips;
    historical M1.5/M2/M3 DoD notes are ignored)

- Plan `.team/plans/ENG-01-dual-runtime.md` marked ENG-01 slices complete
  → `tests/test_eng01_closeout.py::test_eng01_plan_slices_complete`
  — currently failing: status still “Wave 0 architect lock”; ticket-map “T-058 close-out”
    title alone does not count

- Backlog ENG-01 item updated to Done / pending human merge (not “parked”)
  → `tests/test_eng01_closeout.py::test_backlog_eng01_done_pending_human_merge`
  — currently failing: backlog still has **Next** / **Active** ENG-01 framing; no
    Done + pending human merge line for ENG-01

- No merge to `main` by agents
  → `tests/test_eng01_closeout.py::test_eng01_pending_human_merge_not_merged_by_agents`
  — currently failing: no ENG-01/T-058 “complete pending human merge” lock
    (M2/M3 pending-merge lines ignored)

- Do not weaken CI gates
  → `tests/test_eng01_closeout.py::test_ci_quality_gates_not_weakened`
  — currently passing (cov-fail-under=80 + mypy strict already locked)

- T-058 spec AC checkboxes marked done at close-out
  → `tests/test_eng01_closeout.py::test_t058_spec_acceptance_criteria_checked`
  — currently failing: all six T-058 AC items still `[ ]`

## Not covered by tests

- Full AGENTS.md toolchain (ruff / mypy / full pytest + coverage ≥80%) — verifier gate;
  verify by running the commands at close-out and recording in `.team/qa/T-058-verify.md`
- Literally proving git history has no agent merge commit to `main` — process / human;
  tests lock the backlog/close-out *claim* that agents did not merge
- Gathering review/verify blobs from parallel role tips — implementer copies files; tests
  only assert presence on the close-out tip
- Merging web mockup to site production deploy — out of scope per spec

## Unhappy / boundary notes

- Primary QA may remain historically RED if `T-XXX-verify.md` is PASS (or T-058 PASS lists
  the ticket green/DONE); either path satisfies the “qa notes … DONE / green” AC
- T-053 is architect/ADR; still requires a green qa note or aggregated DONE listing
- Review / verify gates apply to implement tips T-054–T-057 (parent brief)
- Non-goal themes must be *asserted* (negation / checked checklist), not merely named
- Changelog must cover both browser interact (demo budgets) and local API iteration in
  client voice (not RPC/micropip/ASGI-only jargon)
- Backlog must flip ENG-01 off **Next** / **Active** / parked into Done pending human merge
