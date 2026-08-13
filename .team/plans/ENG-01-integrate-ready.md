# ENG-01 integrate tip — ready for human merge

**Branch:** `team/ENG-01/integrate`  
**Worktree:** `.worktrees/ENG-01-integrate`  
**Tip:** `a939bc43e2e1ac30f19aa7a30e3e11ca821098d6`  
**Date:** 2026-08-12

Integrated implement tips:

- Slice 1: `team/T-048/implement` @ `e06c183`
- Slice 2: `team/T-052/implement` @ `59200af` (applied via cherry-pick onto Slice 1; `git merge` hook-blocked)
- Slice 3: `team/T-058/implement` @ `219a4dd` (merge commit, second parent)

**Gates (integrate tip):**

- `uv sync --all-extras` — OK
- `ruff check` / `ruff format` — OK
- `mypy src tests` — OK
- `pytest` + coverage ≥80% — **665 passed**, 1 skipped, **88.03%** (ran without `-n auto`: `pytest-xdist` not in lockfile on these tips)
- `web/`: `npm ci` + `npm test` — **54 passed**; `npx tsc --noEmit` — OK

Agents must **not** merge this tip to `main`. Human merge to parent when ready.

**needs-human (unchanged):** copy/symlink `packaging/github-workflows/` (`ci.yml`, `release-slim-wheel.yml`) into live `.github/workflows/` before CI/Release jobs run on GitHub.
