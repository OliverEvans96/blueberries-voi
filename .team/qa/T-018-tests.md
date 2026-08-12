# T-018 test map (RED — M1.5 close-out DoD contracts)

## Coverage of acceptance criteria

- All of T-009–T-017 acceptance criteria are marked done in their specs (or
  explicitly waived with Oliver note in `.team/backlog.md`)
  → `tests/test_m15_closeout.py::test_m15_ticket_spec_acceptance_criteria_done_or_waived`
  — currently failing for T-009, T-010, T-011, T-013, T-016, T-017
  (unchecked AC; T-012/T-014/T-015 already checked or green-path and pass)

- `.team/qa/` contains green records for M1.5 tickets in scope; no open red qa
  blockers without `needs-human`
  → `tests/test_m15_closeout.py::test_m15_ticket_qa_record_green`
  → `tests/test_m15_closeout.py::test_no_open_red_qa_blockers_without_needs_human`
  — currently failing: T-016 RED without needs-human; T-017 missing qa record

- `.team/reviews/` contains APPROVED reviews for the M1.5 implementation waves
  (or equivalent per-ticket reviews covering T-009–T-017)
  → `tests/test_m15_closeout.py::test_m15_ticket_review_approved`
  — currently failing: T-016, T-017 (no subject review); earlier tickets with
  APPROVED reviews pass

- `.team/changelog.md` has a plain-English M1.5 entry (client voice): what the
  filter can observe per rung, that likelihood matches sim physics, and honest
  P0/P1 caveats if Stage A failed there
  → `tests/test_m15_closeout.py::test_changelog_has_m15_client_voice_entry`
  — currently failing: no M1.5 close-out entry yet

- DoD checklist from plan §9 is copied into `.team/reviews/` or a close-out note
  with each item checked (RichObs; rich DayLog; soft LL gone; Stage C generative;
  Stage A multi-rung; Stage B/oracle; L fallback; no CTL/VOI/browser; quality gates)
  → `tests/test_m15_closeout.py::test_dod_checklist_copied_and_checked`
  — currently failing: no close-out DoD note yet
  → `tests/test_m15_closeout.py::test_plan_section_9_dod_still_present`
  — currently passing (plan source still present)

- `uv sync --all-extras && uv run ruff check . && uv run ruff format --check . &&
  uv run mypy src tests && uv run pytest` is green (coverage ≥80%)
  — not covered by unit tests (expensive / CI verifier); verify by running the
  AGENTS.md toolchain and recording results in the close-out review / verifier note

- No production CTL/VOI/browser modules landed under this milestone beyond
  pre-existing stubs
  → `tests/test_m15_closeout.py::test_no_production_ctl_voi_browser_under_m15`
  — currently passing (stubs empty)
  → `tests/test_m15_closeout.py::test_m15_milestone_claims_do_not_assert_ctl_voi_shipped`
  — currently failing: no M1.5 changelog/close-out text yet to assert non-claims against

## Not covered by tests

- Full quality-gate command chain / coverage ≥80% — because slow and belongs to
  verifier; verify by AGENTS.md commands at close-out
- Sign-off owner if Oliver unavailable — open question; document in backlog if blocked
- Whether changelog is one entry vs per-wave rollup — process preference; tests
  accept either an `## … M1.5` heading or M1.5-tagged bullets with required themes

## Unhappy / boundary notes

- Spec AC must be under `## Acceptance criteria` (open-question checkboxes ignored)
- RED QA is allowed only with `needs-human` in the qa file or backlog tied to the ticket
- Review coverage is by filename subject (or M1.5/T-018 close-out spanning T-009–T-017),
  not incidental ticket mentions in other reviews
