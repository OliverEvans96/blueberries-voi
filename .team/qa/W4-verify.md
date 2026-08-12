# Wave 4 verify — T-015 Dynamic L + joint→sliding_window fallback

DATE: 2026-08-12
STATUS: PASS

Scope: T-015 / Wave 4 L-fallback for M1.5. Full-suite red from
T-016 / T-017 / T-018 (and unrelated M1.5 closeout process checks) is
**expected and not counted as a T-015 regression**.

## Commands run

- `uv sync --all-extras` → exit 0, Resolved 125 packages / Checked 119 packages
- `uv run ruff check .` → exit 0, All checks passed
- `uv run ruff format --check .` → exit 0, 55 files already formatted
- `uv run mypy src tests` → exit 0, Success: no issues found in 35 source files
- `uv run pytest tests/test_l_fallback.py -v --no-cov` → exit 0, **13 passed**
- `uv run pytest tests/test_l_fallback.py tests/test_filter.py -q --no-cov` → exit 0, **21 passed**
- `uv run pytest -q` → exit 1, **36 failed, 150 passed, 1 skipped**, coverage 82.50% (≥80%); failures are T-016/T-017/T-018 RED + M1.5 closeout process (see below), not `test_l_fallback` / filter L-fallback
- Closeout slice `-k "T-015 or l_fallback or 015"` → exit 0, **3 passed**

Artifacts claimed APPROVED present:
- `.team/qa/T-015.md` (STATUS: PASS)
- `.team/reviews/T-015.md` (STATUS: APPROVED)
- `experiments/m15_l_remeasure.md` (M1.5 L remeasure + fallback note)

## Acceptance criteria (T-015)

- [x] RBPF (or factory) selects **`full_joint`** when `joint_state_count(K, L, N) ≤ MAX_JOINT_FLOATS` — verified by `tests/test_l_fallback.py` (`test_choose_backend_selects_full_joint_*`, `test_rbpf_within_budget_uses_full_joint`)
- [x] When L would exceed the budget, backend becomes **`sliding_window`** and a structured return field records `{K, L, N, joint_floats, backend="sliding_window", reason=...}` — verified by `test_choose_backend_falls_back_*`, `test_fallback_choice_records_structured_reason_fields`, `test_rbpf_over_budget_*`, `test_rbpf_initialize_over_budget_*`
- [x] Silent L truncation impossible on production path; L used equals requested/empirical L (or fallback backend) — verified by `test_choose_backend_never_silently_truncates_l`, initialize/over-budget RBPF tests
- [x] Dynamic L: filter track length follows configured max under joint when within budget — verified by `test_dynamic_l_follows_configured_max_when_joint_fits`
- [x] Short bakeoff / note addendum under `experiments/` documents re-measured L + fallback — verified by `test_m15_l_remeasure_experiment_note_documents_fallback` + file present
- [x] FIL-12=B not reopened; sliding_window is FIL-13 fallback — verified by `test_production_default_remains_full_joint_fil12_not_reopened`
- [x] Quality gates green **for T-015 / Wave 4 scope** — ruff, format, mypy clean; scoped L-fallback + related filter tests green. Full `pytest` red labeled below (not T-015).

## Full-suite red (out of scope for Wave 4 / T-015)

Not a T-015 regression. Observed failures:

- **T-016 / Stage A** — `tests/test_stage_a_multirung.py` (e.g. CTL surface assert) + closeout QA/review RED for T-016
- **T-017 / Stage B + oracle** — `tests/test_stage_b_oracle.py` (missing exports / schema; RED expected)
- **T-018 / M1.5 closeout process** — open RED QA without needs-human, missing reviews, changelog/DoD claims
- Unrelated closeout checkbox failures for older tickets (T-009, T-010, T-011, T-013) in `tests/test_m15_closeout.py`

No failures in `tests/test_l_fallback.py` or related filter L-fallback coverage.

## Incomplete

(none for T-015 / Wave 4 scoped must-pass)
