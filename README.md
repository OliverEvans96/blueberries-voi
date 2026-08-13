# blueberries-voi

Simulation, analysis, and visualization for blueberry value-of-information (VOI)
work — a typed Python package with CLI scripts and optional Jupyter notebooks.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+. For the optional
pytest-testmon cache seed, also install [Git LFS](https://git-lfs.com/) and run
`git lfs install` / `git lfs pull` after clone so `.testmondata` is a real SQLite
file (not a pointer).

```bash
uv sync --all-extras
```

## Quality gates

Full verify / CI-style gate (coverage + xdist; **no** testmon selection):

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Everyday loops (no coverage):

```bash
uv run pytest                 # full suite
uv run pytest --testmon       # deselect tests unaffected by local edits
./scripts/refresh-testmon.sh  # rebuild LFS-tracked .testmondata after a green tip
```

See `AGENTS.md` for the role gate ladder, conflict policy, and LFS notes.

## Notebooks

```bash
uv sync --extra notebooks
uv run jupyter lab
```

Put notebooks under `notebooks/` and import `blueberries_voi` rather than
copying logic into cells.

## CLI

```bash
uv run blueberries-voi --help
uv run python -m blueberries_voi --version
```

## Team workflow

This repo follows the agent-dev-team protocol. Project state lives in `.team/`
(intake, specs, ADRs, reviews, QA reports, changelog). See `AGENTS.md`.

## Browser / Pyodide packaging

The slim interactive wheel is distributed via **GitHub Release** (not PyPI).
See [`packaging/README.md`](packaging/README.md) for the `micropip.install`
Release URL pattern, Pyodide **314.0.4** / CPython **3.14.2** pins, and the
note about copying canonical workflows from `packaging/github-workflows/` into
the live GitHub Actions workflows directory.

