# Wave 3 verification — T-013 + T-014 (M1.5)

DATE: 2026-08-12
STATUS: **FAIL**

Claimed: T-013 and T-014 GREEN + APPROVED
(`.team/qa/T-013.md`, `.team/reviews/T-013.md`, `.team/qa/T-014.md`,
`.team/reviews/T-014.md`).

Full-repo AGENTS.md toolchain does **not** exit clean. Failures are entirely
from in-flight sibling RED suites (**T-016**, **T-017**). Wave-3 owned scoped
proof is fully green; **no T-013 / T-014 regressions**.

## Commands run

| Command | Exit | Result |
|---------|------|--------|
| `uv sync --all-extras` | 0 | Resolved 125 packages; 119 checked |
| `uv run ruff check .` | 1 | 7 errors, all in `tests/test_stage_b_oracle.py` (T-017) |
| `uv run ruff format --check .` | 1 | 1 file would be reformatted: `tests/test_stage_b_oracle.py` (T-017) |
| `uv run mypy src tests` | 1 | 2 errors: unused `type: ignore` in `tests/test_stage_b_oracle.py` (T-017) |
| `uv run pytest` | 1 | **36 failed**, 117 passed, 1 skipped; coverage **87.00%** (≥80%) |

## Scoped Wave-3 proof (required)

```bash
uv run pytest tests/test_arrival_priors.py tests/test_lot_resolved_ll.py -q --no-cov
→ 19 passed (9 + 10)

uv run ruff check src/blueberries_voi/filter/arrival_priors.py \
  src/blueberries_voi/filter/backends.py \
  src/blueberries_voi/filter/__init__.py \
  tests/test_arrival_priors.py tests/test_lot_resolved_ll.py
→ All checks passed

uv run mypy src/blueberries_voi/filter/arrival_priors.py \
  src/blueberries_voi/filter/backends.py \
  src/blueberries_voi/filter/__init__.py \
  tests/test_arrival_priors.py tests/test_lot_resolved_ll.py
→ Success: no issues found in 5 source files
```

## Failure attribution

### Sibling RED — 36/36 pytest failures; all lint/type redness

| Ticket | File | Failed | Notes |
|--------|------|--------|-------|
| T-016 | `tests/test_stage_a_multirung.py` | 15 | RED: missing `run_m15_stage_a` / schemas / Stage A docs hooks |
| T-017 | `tests/test_stage_b_oracle.py` | 21 | RED: missing Stage B / oracle ladder surface; **sole** ruff + format + mypy breakages |

### Named siblings checked (user list)

| Ticket | Observed at verify time |
|--------|-------------------------|
| T-012 Stage C | **Green** — `tests/test_stage_c_generative.py` + related: 20 passed, 1 skip (optional aux). QA `STATUS: PASS`. |
| T-015 L-fallback | **Green** — `tests/test_l_fallback.py` green in full run; QA now `STATUS: PASS`. |
| T-016 Stage A | **RED** — 15 failures (above). |
| T-017 Stage B/oracle | **RED** — 21 failures + all repo ruff/format/mypy redness (beyond the named T-012/T-015/T-016 list). |

### T-013 / T-014 regressions

**None.** Zero failures in `tests/test_arrival_priors.py` or
`tests/test_lot_resolved_ll.py`. Owned filter paths pass scoped ruff + mypy.

## T-013 acceptance criteria (observed)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| F2a prior narrower than cold Abdella (SD/HPD) | OK | `test_f2a_prior_narrower_than_cold_abdella_mix`, mask inject tests |
| F2 concentrates on measured τ_in bin | OK | `test_arrival_age_prior_f2_exists_and_concentrates_on_measured_bin`, F2 mask inject |
| P0/P1 UNOBSERVED → cold Abdella; F2a/F2 do not fire | OK | `test_p0_p1_delivery_prior_matches_cold_abdella_mix` |
| No new sales/waste soft LL terms; birth prior only | OK | weights-unchanged + AST soft-term guard |
| F2 tighter than F2a on same fixture | OK | `test_f2_tighter_than_f2a_on_same_fixture` |
| Quality gates green (owned paths) | OK | scoped ruff/mypy/pytest above |
| Quality gates green (full repo) | **FAIL** | sibling T-016/T-017 only |

## T-014 acceptance criteria (observed)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `sales_by_lot` scored; lot-A > lot-B leakage bound | OK | sales LL + leakage + count-shift tests |
| `waste_by_lot` scored; analogous leakage | OK | waste LL + leakage tests |
| UNOBSERVED maps = totals-only; `{}` ≠ UNOBSERVED | OK | unobserved + empty-map tests |
| F1 ρ=1 complete maps; biased-ρ absent/non-gate | OK | rho-one + biased-sampler tests |
| One RBPF / one `observation_loglik_mc` | OK | `test_single_rbpf_class_and_one_mc_ll_entrypoint` |
| Quality gates green (owned paths) | OK | scoped ruff/mypy/pytest above |
| Quality gates green (full repo) | **FAIL** | sibling T-016/T-017 only |

## Numbers

- Coverage: **87.00%** (threshold 80%)
- Pytest: **117 passed / 36 failed / 1 skipped**
- Wave-3 scoped: **19 passed / 0 failed**
- Sibling RED share: **36/36** failures; lint/type: **100%** from T-017 test file

## Verdict

**FAIL** — AGENTS.md full-repo toolchain is not green.

Wave-3 claims (T-013 + T-014 APPROVED) are **supported for owned behaviour**:
scoped arrival-prior and lot-resolved-LL suites are fully green with clean
owned-path ruff/mypy. Repo redness is **only** intentional sibling RED for
**T-016** (Stage A) and **T-017** (Stage B / oracle), not T-013/T-014
regressions. T-012 and T-015 are green at verify time.
