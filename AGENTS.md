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
| Tests | **pytest** (+ **pytest-xdist** / branch coverage on verify·CI) |
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

Everyday `pytest` is **fast**: no coverage plugin in default `addopts`. Coverage
≥80% and xdist apply only on the **verify / CI** rung.

| Role | Gates |
|------|--------|
| **qa** | `uv sync` once → `uv run pytest <new tests> --no-cov` (prove RED) |
| **implement** | Ticket tests with `--no-cov` in the red/green loop; `ruff` / `mypy` on touched paths (or full tree if cheap); optional one full verify-style `pytest` with coverage before handoff |
| **review** | No pytest |
| **verify / CI** | `ruff` + `mypy` + **full** pytest **with** coverage ≥80% and xdist (command below) |

## Toolchain (verify / before push)

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Pip-equivalent (matches CI):

```bash
pip install -e ".[dev]"
ruff check .
ruff format .
mypy src tests
pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Fast day-to-day (no coverage):

```bash
uv run pytest                    # full suite, no cov
uv run pytest tests/test_foo.py --no-cov   # ticket slice / RED proof
```

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

## Project layout

```
src/blueberries_voi/   # installable package + CLI
tests/                 # mirrors package modules (test_<module>.py)
notebooks/             # exploration; import the package
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

## CI

GitHub Actions runs Ruff, Mypy, and pytest with xdist + coverage on Python 3.11
and 3.12. A pull request is not complete until CI is green.

## Summary for agents

**Write tests first. Keep mypy strict and ruff clean. Keep coverage ≥80% on
verify/CI. Prefer library code over notebook-only logic. Never "fix" failures
by weakening configuration. Use the role gate ladder — do not run full coverage
on every qa/implement loop.**
