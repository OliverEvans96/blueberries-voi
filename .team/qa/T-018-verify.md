# T-018 verify — M1.5 close-out

DATE: 2026-08-12
STATUS: PASS

## Commands run

- `uv sync --all-extras` → exit 0, Resolved 125 packages; Checked 119 packages
- `uv run ruff check .` → exit 0, All checks passed!
- `uv run ruff format --check .` → exit 0, 59 files already formatted
- `uv run mypy src tests` → exit 0, Success: no issues found in 37 source files
- `uv run pytest` → exit 0, **194 passed, 1 skipped**; coverage **88.75%** (≥80%)

## Acceptance criteria

- [x] All of T-009–T-017 acceptance criteria are marked done in their specs (or explicitly waived with Oliver note in `.team/backlog.md`) — verified by reading specs T-009–T-017 AC checkboxes (`[x]` on acceptance criteria; open questions remain unchecked as expected); F2a Stage A gap is `needs-human` in `.team/backlog.md`
- [x] `.team/qa/` contains green records for M1.5 tickets in scope; no open red qa blockers without `needs-human` — verified: T-009–T-018 QA STATUS PASS; F2a documented needs-human
- [x] `.team/reviews/` contains APPROVED reviews for the M1.5 implementation waves — verified: T-009–T-010 combined + T-011–T-018 APPROVED; `.team/reviews/M1.5.md` DoD checklist all `[x]`
- [x] `.team/changelog.md` has a plain-English M1.5 entry — verified: `## 2026-08-12 — M1.5 filter complete…` covers rungs/obs, physics-honest LL, P0/P1/F2a caveats, F2 + oracle (T-018); left as-is (no rewrite)
- [x] DoD checklist from plan §9 copied into `.team/reviews/` with each item checked — verified: `.team/reviews/M1.5.md`
- [x] AGENTS.md toolchain green (coverage ≥80%) — verified by commands above; Total coverage: 88.75%
- [x] No production CTL/VOI/browser modules beyond pre-existing stubs — verified: `controller/__init__.py` and `voi/__init__.py` are empty stubs; no browser package under `src/`

## Incomplete

- None. F2a pack_date emit remains `needs-human` in backlog (honest, allowed; not an M1.5 DoD reopen).

## Notes

- Skip: `tests/test_stage_c_generative.py` optional ResearchParticleFilter-vs-brute auxiliary (documented).
- Claimed QA PASS / review APPROVED for T-018 reconfirmed against live toolchain.
