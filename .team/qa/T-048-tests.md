# T-048 test map (RED — Slice 1 close-out DoD contracts)

## Coverage of acceptance criteria

- `.team/qa/` (or ticket qa notes) records Slice-1 tickets T-043–T-047 as green / DONE
  → `tests/test_slice1_closeout.py::test_slice1_ticket_qa_or_verify_green`
  — currently failing: primary QA files still STATUS RED; no `T-XXX-verify.md` on tip
  → `tests/test_slice1_closeout.py::test_slice1_ticket_verify_pass_artifact_present`
  — currently failing: missing `.team/qa/T-043-verify.md` … `T-047-verify.md`
  (gather from `team/T-04X/verify`; T-047 verify tip `@ c47f42a`)

- `.team/reviews/` APPROVED for T-043–T-047 (DoD / parent brief)
  → `tests/test_slice1_closeout.py::test_slice1_ticket_review_approved`
  — currently failing: no review artifacts on implement tip (copy from `team/T-04X/review`)

- `.team/changelog.md` gains a plain-English entry that the interactive Python engine can
  run in a browser worker under demo budgets (no jargon-only bullet)
  → `tests/test_slice1_closeout.py::test_changelog_has_slice1_client_voice_entry`
  — currently failing: no Slice-1 / browser-worker close-out entry yet

- Close-out checklist asserts non-goals still hold: no full WASM rewrite; no matplotlib /
  pyarrow in browser path; no production-N-in-tab claim; API implement not required for
  Slice-1 DONE
  → `tests/test_slice1_closeout.py::test_slice1_closeout_nongoals_checklist`
  — currently failing: no Slice-1 close-out DoD / non-goal note under `.team/reviews/`
    (RED `.team/qa/T-048.md` is excluded until STATUS flips)

- Plan `.team/plans/ENG-01-dual-runtime.md` Slice-1 waves marked complete (or status note)
  → `tests/test_slice1_closeout.py::test_eng01_plan_slice1_waves_complete`
  — currently failing: status still “Wave 0 architect lock”; ticket-map “T-048 close-out”
    title alone does not count

- No merge to `main` performed by agents
  → `tests/test_slice1_closeout.py::test_slice1_pending_human_merge_not_merged_by_agents`
  — currently failing: no Slice-1/T-048 “complete pending human merge” lock (M2/M3 lines ignored)

- Do not weaken CI gates
  → `tests/test_slice1_closeout.py::test_ci_quality_gates_not_weakened`
  — currently passing (cov-fail-under=80 + mypy strict already locked)

- T-048 spec AC checkboxes marked done at close-out
  → `tests/test_slice1_closeout.py::test_t048_spec_acceptance_criteria_checked`
  — currently failing: all five T-048 AC items still `[ ]`

## Not covered by tests

- Full AGENTS.md toolchain (ruff / mypy / full pytest + coverage ≥80%) — verifier gate;
  verify by running the commands at close-out and recording in `.team/qa/T-048-verify.md`
- Literally proving git history has no agent merge commit to `main` — process / human;
  tests lock the backlog/close-out *claim* that agents did not merge
- Gathering review/verify blobs from parallel role tips — implementer copies files; tests
  only assert presence on the close-out tip

## Unhappy / boundary notes

- Primary QA may remain historically RED if `T-XXX-verify.md` is PASS (or T-048 PASS lists
  the ticket green/DONE); either path satisfies the “qa or ticket qa notes” AC
- Review coverage is by filename subject tokens or Slice-1 / ENG-01 close-out spanning
  T-043–T-047, not incidental mentions in unrelated reviews
- Non-goal themes must be *asserted* (negation / checked checklist), not merely named
- Changelog must mention browser/worker + interactive engine + demo/dialed budgets in
  client voice (not RPC/micropip-only jargon)
