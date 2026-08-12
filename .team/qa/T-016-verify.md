# T-016 verify — Multi-rung Stage A (shared CRN)

DATE: 2026-08-12
STATUS: PASS

Scope: T-016 / M2.5 multi-rung Stage A. Full-suite red from T-017 RED /
in-flight Stage B+oracle and T-018 closeout process checks is **expected and
not counted as a T-016 regression**. Claimed APPROVED artifacts present:
`.team/qa/T-016.md` (PASS), `.team/reviews/T-016.md` (APPROVED).

## Commands run

- `uv sync --all-extras` → exit 0, Resolved 125 packages / Checked 119 packages
- `uv run ruff check .` → exit 0, All checks passed
- `uv run ruff format --check .` → exit 0, 57 files already formatted
- `uv run mypy src tests` → exit 0, Success: no issues found in 36 source files
- `uv run pytest tests/test_stage_a_multirung.py -q --no-cov` → exit 0, **15 passed**
- `uv run pytest` → exit 1, **32 failed, 154 passed, 1 skipped**; failures are
  T-017 / T-018 closeout (labeled below), not `test_stage_a_multirung`
- Live smoke: `run_m25_stage_a(root_seed=0)` → six rungs; F2 contracts
  (`posterior_sd=0.0`); P0/P1/F1/F1s/F2a uncontracted — matches
  `experiments/m25_stage_a_result.md`

## Acceptance criteria

- [x] Runnable experiment covers rungs **{P0, P1, F1, F1s, F2a, F2}** with a
  **shared** `root_seed` / SIM-05 streams; only the observation mask differs —
  verified by `tests/test_stage_a_multirung.py` (export / default rungs /
  shared seed) + live smoke six rows under one `root_seed=0`
- [x] Each rung reports prior vs posterior arrival-age spread (cohort-from-birth
  metric documented) and a boolean/pass flag using a documented margin plus
  tight-prior control collapse — verified by schema / margin / cohort-doc tests
  + smoke table columns `prior_sd` / `posterior_sd` / `contracted` /
  `tight_control`
- [x] Result MD under `experiments/` publishes a plain table; **P0/P1 FAIL
  allowed** if documented; higher-rung honesty when they fail — verified by
  `experiments/m25_stage_a_result.md` present; P0/P1 FAIL (allowed); F2a FAIL
  labeled **needs-human**; F2 PASS
- [x] Figures land under `figures/m2.5/` with README mapping figure → rung /
  FIL-11 — verified by `figures/m2.5/m25_stage_a_rung_map.png` +
  `figures/m2.5/README.md` Stage A map table
- [x] Does not claim VOI dollars; no CTL code — verified by
  `test_no_voi_dollars_or_ctl_in_stage_a_surface` + result MD disclaimer
- [x] Quality gates green for T-016 scope — ruff, format, mypy clean; scoped
  `tests/test_stage_a_multirung.py` green. Full `pytest` red labeled below
  (not T-016 functional)

## Full-suite red (out of scope for T-016)

Not a T-016 library/regression failure. Observed failures:

- **T-017 / Stage B + oracle** — all `tests/test_stage_b_oracle.py` RED
  (missing exports / MD / figure map); expected in-flight or RED ticket
- **T-018 / M2.5 closeout** — unchecked AC checkboxes on several specs
  (including T-016’s still-`[ ]` boxes in `.team/specs/T-016.md`), T-017 QA
  RED without needs-human, missing T-017 review, changelog/DoD process
- Closeout also fails `test_m25_ticket_spec_acceptance_criteria_done_or_waived[T-016]`
  solely because spec checkboxes were never flipped to `[x]` — process debt,
  not a Stage A runtime regression (`test_stage_a_multirung.py` is green)

**No T-016 regression:** `tests/test_stage_a_multirung.py` **15/15** in both
scoped and full runs.

## Incomplete

(none for T-016 functional scope)

## Notes — F2a needs-human

Smoke table still records F2a FAIL as **needs-human** (sim does not yet emit
ASN `pack_date` on `DayLog`). That honesty is present in
`experiments/m25_stage_a_result.md` and matches live smoke.

**Gap:** `.team/backlog.md` has **no** F2a / `pack_date` / T-016 needs-human
escalation entry. Human follow-up should add one if the sim gap remains open
(verifier does not implement).
