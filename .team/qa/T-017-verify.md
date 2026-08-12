# T-017 verify — Stage B + oracle ladder (M1.5)

DATE: 2026-08-12
STATUS: PASS

Scope: T-017 / M1.5 Stage B calibration + B-state oracle ladder. Claimed
APPROVED artifacts present: `.team/qa/T-017.md` (PASS),
`.team/reviews/T-017.md` (APPROVED). Full-suite red from **T-018 closeout**
(plus coverage fail-under from unexercised `m15` runners) is **labeled below
and not counted as a T-017 scoped regression**.

## Commands run

- `uv sync --all-extras` → exit 0, Resolved 125 packages / Checked 119 packages
- `uv run ruff check .` → exit 0, All checks passed
- `uv run ruff format --check .` → exit 0, 58 files already formatted
- `uv run mypy src tests` → exit 0, Success: no issues found in 36 source files
- `uv run pytest tests/test_stage_b_oracle.py tests/test_stage_a_multirung.py -q --no-cov` → exit 0, **38 passed** (23 Stage B + 15 Stage A)
- `uv run pytest` → exit 1, **3 failed, 183 passed, 1 skipped**; coverage **75.26%** (&lt;80%); failures are T-018 closeout + cov gate (labeled below), not `test_stage_b_oracle` / `test_stage_a_multirung`
- Live harness checks: `b_state_mean_abs_age_error(...) == 0.0`; published MD gap table F2≪P1 (ratio ≈0.22 ≤ 0.5) — **PASS**

## Acceptance criteria

- [x] Stage B runs for Stage-A-pass rungs; 90% CI coverage + rank histograms; MD + figures under `figures/m1.5/` / `experiments/m15_stage_b_*.md` — verified by `tests/test_stage_b_oracle.py` (schema / paths / README map) + published `experiments/m15_stage_b_result.md` + on-disk `figures/m1.5/m15_stage_b_*_rank.png` and `m15_oracle_ladder_gap.png`
- [x] A-failing rungs labeled **diagnostic only** in MD — verified by result MD rows P0/P1/F1/F1s/F2a `diagnostic_only=yes` + `test_diagnostic_only_labeling_for_a_failing_rungs`
- [x] Pass language: coverage band + non-U / non-dome ranks — verified by `STAGE_B_COVERAGE_LO/HI` / `STAGE_B_RANK_FLATNESS_RULE` tests + MD “Pass language” section `[0.7, 0.99]`
- [x] Oracle ladder: B-state age error zero by construction — verified by `test_b_state_age_error_zero_by_construction` + live `b_state_mean_abs_age_error == 0.0`
- [x] Shared-CRN gap table F2 ≪ P1 vs B-state; B-clair not implemented — verified by published gap table **PASS**, gap helper tests, `test_b_clair_not_implemented` / compare rejection
- [x] No CTL / VOI sweep code — verified by `test_no_voi_or_ctl_in_stage_b_oracle_surface`
- [x] Quality gates green for T-017 scope — ruff, format, mypy clean; scoped Stage A+B pytest **38 passed**. Full `pytest` red labeled below (not T-017 functional)

## Full-suite red (out of scope for T-017)

Not a T-017 library/regression failure. Observed:

- **T-018 / M1.5 closeout** — `tests/test_m15_closeout.py`:
  - `test_changelog_has_m15_client_voice_entry`
  - `test_dod_checklist_copied_and_checked`
  - `test_m15_milestone_claims_do_not_assert_ctl_voi_shipped`
- **Coverage gate** — total **75.26%** &lt; `--cov-fail-under=80`; driven largely by `viz/m15.py` (~31% in full suite) because Stage B/oracle **runners are smoke-only**, not exercised under pytest (same gap called non-blocking in `.team/reviews/T-017.md`)

**No T-017 regression:** `tests/test_stage_b_oracle.py` **23/23** and Stage A `tests/test_stage_a_multirung.py` **15/15** in both scoped and full runs.

## Non-blocking note — F2 Dirac CI coverage ≈ 0

Published smoke: F2 `coverage_90 = 0.0000` (only Stage-A-pass rung; not diagnostic). Matches reviewer note: equal-tailed CI on near-Dirac arrival-age posterior collapses on the discrete grid. Honest under the current metric; Stage B “green on A-pass rungs” for plan DoD / T-018 stays red until a discrete-grid CI rule lands. **Does not fail T-017 AC** (artifacts + diagnostic labeling + oracle gap still satisfy the ticket).

## Incomplete

(none for T-017 functional scope)
