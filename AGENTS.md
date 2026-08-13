# Agent instructions (mandatory)

This repository uses **test-driven development**, **static typing**, **automated
quality gates**, and the **agent-dev-team** protocol (state in `.team/`). Treat
this document as **binding** for any code change.

## What this project is

Python package for **simulation, analysis, and visualization** related to
blueberry value-of-information (VOI) work. Installable library code and CLI live
under `src/blueberries_voi/`; exploratory work may live in `notebooks/` that
import the package.

## Architecture (short)

1. **Library first**: reusable simulation/analysis code is a typed package under
   `src/blueberries_voi/`, installed editable via `uv`.
2. **Scripts**: CLI entry points (`blueberries-voi` / `python -m blueberries_voi`)
   call into the library; they stay thin.
3. **Notebooks**: under `notebooks/`, for exploration and figures; they import
   the installed package rather than duplicating logic. Notebooks are not part of
   the coverage or mypy gates.

## Stack

| Piece | Choice |
|-------|--------|
| Env / lockfile | **uv** (`uv.lock` committed) |
| Python | **3.11+** (CI: 3.11, 3.12) |
| Layout | **src/** package `blueberries_voi` |
| Lint / format | **Ruff** |
| Types | **Mypy** strict |
| Tests | **pytest** (+ **pytest-xdist** / branch coverage on verify·CI; optional **pytest-testmon**) |
| Notebooks | optional extra `[notebooks]` (Jupyter + ipykernel) |
| Team process | **agent-dev-team** → `.team/` |

## Non-negotiable workflow: TDD

1. **Red**: Write a **failing** automated test that specifies the desired behavior.
2. **Green**: Implement the **smallest** change that makes the test pass.
3. **Refactor**: Improve structure and names while keeping tests green.

### Rules

- **No production code without a preceding test** unless the change is purely
  mechanical and does not alter behavior. When in doubt, add a test first.
- **Regression tests are required** for every bug fix.
- **Do not** `@pytest.mark.skip` without a documented, time-bounded reason and a
  tracking reference.
- **Do not** lower coverage thresholds or relax `mypy` / `ruff` to pass CI.
- New modules, dependencies, or public interfaces → **architect** (ADR + spec)
  before implementation; **qa** writes failing tests before production code.

## Role gate ladder

Everyday `pytest` is **fast**: no coverage and no testmon in default `addopts`.
Coverage ≥80% and xdist apply only on the **verify / CI** rung. Testmon is
opt-in for implement loops (see below).

| Role | Gates |
|------|--------|
| **qa** | `uv sync` once → `uv run pytest <new tests> --no-cov` (prove RED; **no** `--testmon`) |
| **implement** | Prefer `uv run pytest --testmon` (or ticket path without testmon) with `--no-cov` in the red/green loop; `ruff` / `mypy` on touched paths; optional/recommended `./scripts/refresh-testmon.sh` then commit `.testmondata` if changed before handoff; optional one full verify-style `pytest` with coverage before handoff |
| **review** | No pytest |
| **verify / CI** | `ruff` + `mypy` + **full** pytest **with** coverage ≥80% and xdist (command below). **No testmon selection** (`--no-testmon` if `addopts` ever gains `--testmon`). Does **not** refresh `.testmondata` in MVP |

## Toolchain (verify / before push)

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Pip-equivalent (matches the intended CI gate):

```bash
pip install -e ".[dev]"
ruff check .
ruff format .
mypy src tests
pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Fast day-to-day (no coverage):

```bash
uv run pytest                    # full suite, no cov, no testmon
uv run pytest --testmon          # implement: deselect unaffected tests
uv run pytest tests/test_foo.py --no-cov   # ticket slice / RED proof
./scripts/refresh-testmon.sh     # after green tip: rebuild LFS seed (no cov)
```

### Testmon cache (`.testmondata`)

- Seed is **Git LFS–tracked** (best-effort fingerprints across worktrees). After
  `git worktree add` / clone, run `git lfs install` and `git lfs pull` so
  `.testmondata` is a real SQLite file — not a pointer. Pointer / missing DB →
  full `--testmon` collect (OK fallback).
- Refresh only via `./scripts/refresh-testmon.sh` (**no** `--cov`; coverage forces
  testmon nocollect). Script checkpoints WAL into a single file; never commit
  `.testmondata-wal` / `.testmondata-shm`.
- Merge conflicts: take one side (`./scripts/resolve-testmon-conflict.sh ours|theirs`
  or `git checkout --ours/--theirs -- .testmondata && git add .testmondata`). Never
  hand-merge SQLite; never block a ticket on cache merge.
- Default `addopts` must stay free of `--testmon` and `--cov`.

Notebooks:

```bash
uv sync --extra notebooks
uv run jupyter lab
# or: uv run python -m ipykernel install --user --name=blueberries-voi
```

## Quality bar

| Requirement | Standard |
|-------------|----------|
| Formatter / linter | **Ruff** — must pass |
| Types | **Mypy** strict on `src` and `tests` |
| Tests | **pytest**; verify/CI also use **pytest-xdist** (`-n auto`) |
| Coverage | **≥80%** on `blueberries_voi` on verify/CI only (`--cov-fail-under=80`) |
| Testmon | Optional implement speedup; never shrinks the verify/CI gate |

## Project layout

```
src/blueberries_voi/   # installable package + CLI
tests/                 # mirrors package modules (test_<module>.py)
notebooks/             # exploration; import the package
scripts/               # helpers (e.g. refresh-testmon.sh)
.team/                 # intake, specs, ADRs, reviews, qa, changelog
```

## agent-dev-team state

Roles are done when their files exist under `.team/`, not when an agent claims
done. Definition of done: acceptance criteria pass · `.team/reviews/` APPROVED ·
`.team/qa/` green · `.team/changelog.md` has a plain-English entry.

## Don't

- Don't put simulation/analysis logic only in notebooks — promote shared code
  into the package with tests.
- Don't add runtime dependencies without an ADR justifying them.
- Don't commit secrets, large raw data, or generated outputs (use `.data/` /
  `outputs/` locally; they are gitignored).
- Don't merge, force-push, or weaken CI gates.
- Don't skip architect → qa → implement → reviewer → verifier for feature work.
- Don't rely on testmon deselection for verify/CI coverage; don't commit
  testmon WAL/SHM sidecars.

## CI

GitHub Actions should run Ruff, Mypy, and pytest with xdist + coverage on Python
3.11 and 3.12 (same full command as the verify toolchain above — **no**
`--testmon`). A pull request is not complete until CI is green. If the workflow
file still invokes bare `pytest`, update it to the explicit cov+xdist command
(workflow edits are a human / privileged step when agents are blocked from
`.github/workflows/`).

## Summary for agents

**Write tests first. Keep mypy strict and ruff clean. Keep coverage ≥80% on
verify/CI. Prefer library code over notebook-only logic. Never "fix" failures
by weakening configuration. Use the role gate ladder — do not run full coverage
on every qa/implement loop. Use `--testmon` for implement speed; refresh the LFS
seed without `--cov`; never let testmon shrink the verify/CI gate.**
