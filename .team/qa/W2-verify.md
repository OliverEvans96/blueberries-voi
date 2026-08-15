# Wave 2 verification — T-011 (M1.5 filter)

DATE: 2026-08-12
STATUS: **FAIL**

Claimed: T-011 GREEN + APPROVED (`.team/qa/T-011.md`, `.team/reviews/T-011.md`).
Full-repo AGENTS.md toolchain does **not** exit clean. Failures are almost entirely
sibling Wave-2 RED suites (T-012 / T-013 / T-014). T-011-owned acceptance tests
remain green. One non-sibling residual: soft Stage C smoke over tolerance.

## Commands run

| Command | Exit | Result |
|---------|------|--------|
| `uv sync --all-extras` | 0 | Resolved 125 packages; 119 checked |
| `uv run ruff check .` | 1 | 6× RUF001/002/003 in `tests/test_lot_resolved_ll.py` (ambiguous `ρ`) |
| `uv run ruff format --check .` | 0 | 47 files already formatted |
| `uv run mypy src tests` | 1 | 1 error: `tests/test_lot_resolved_ll.py:70` `no-any-return` |
| `uv run pytest` | 1 | **22 failed**, 80 passed, 1 skipped; coverage **85.11%** (≥80%) |

## Failure attribution

### Sibling RED (expected while T-012/T-013/T-014 implement) — 21 failures

| Ticket | File | Failed | Notes |
|--------|------|--------|-------|
| T-012 | `tests/test_stage_c_generative.py` | 7 (+1 skip) | Missing generative kwargs / contract; soft `tv_vs_exact` still named; no `figures/m1.5/README.md` |
| T-013 | `tests/test_arrival_priors.py` | 8 | `arrival_age_prior_f2a` / `f2` absent; P0/P1/F2a/F2 prior injection not wired |
| T-014 | `tests/test_lot_resolved_ll.py` | 6 | Lot-map LL not scored; also sole ruff + mypy breakages |

### Not sibling RED — 1 failure (T-011 / T-012 boundary)

| Test | Observation |
|------|-------------|
| `tests/test_fil11.py::test_stage_c_smoke` | Deterministic: `result.tv ≈ 0.0533` (not `< 0.05`); `passed=False`. Re-ran 3× same. Soft `tv_vs_exact` path still used by `run_fil11_stage_c` (quarantined NON-GATE per T-011; generative rewrite is T-012). Smoke still hard-gates old soft TV. **Not** a T-013/T-014 RED. |

`test_stage_c_suite_l2_l3` still passes (asserts consistency of `passed` vs TV map, not that TV clears the tol).

## T-011 acceptance criteria (observed)

T-011 core suite (not full repo):

```bash
uv run pytest tests/test_mc_likelihood.py tests/test_filter.py tests/test_rich_obs.py -q --no-cov
→ 35 passed
```

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Soft powers / Gaussian LL off production `_particle_filter_update` / BootstrapPF | OK | `test_mc_likelihood` green |
| Weights from `observation_loglik_mc` + shared kernels | OK | same |
| Skip `UNOBSERVED`; P0 vs P1 divergence | OK | same + `test_rich_obs` / filter |
| No Wallenius density in production | OK | AST/source tests in mc_likelihood |
| Default `n_mc=1`; `FilterSummary.ess` | OK | mc_likelihood |
| Soft Stage C tautology quarantined (not production Stage C gate) | Partial | Doc/NON-GATE + T-012 RED; **`test_stage_c_smoke` still enforces soft TV and fails** |
| ENG-02 same `day_step` symbol | OK | mc_likelihood |
| Quality gates green; coverage ≥80% | **FAIL at repo level** | ruff/mypy/pytest red from siblings; coverage 85.11% OK |

## Numbers

- Coverage: **85.11%** (threshold 80%)
- Pytest: **80 passed / 22 failed / 1 skipped** (103 collected)
- T-011 core: **35 passed** (`mc_likelihood` + `filter` + `rich_obs`)
- Sibling RED share: **21/22** failures; lint/type: **all** from T-014 test file

## Verdict

**FAIL** — AGENTS.md toolchain is not green.

T-011 claimed GREEN is **supported for owned filter/MC-LL behaviour** (35/35 core tests).
Repo redness is **dominated by intentional Wave-2 RED tests** for T-012/T-013/T-014
(plus T-014 ruff/mypy). Flag separately: soft Stage C smoke TV **0.053 > 0.05** —
residual gate on quarantined path, owned by T-012 rewrite / smoke update, not by
arrival priors or lot LL work.

Do not treat this FAIL as a T-011 production MC-LL regression without further
evidence beyond `test_stage_c_smoke`.
