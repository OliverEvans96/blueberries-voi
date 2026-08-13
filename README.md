# blueberries-voi

Simulation, analysis, and visualization for blueberry value-of-information (VOI)
work — a typed Python package with CLI scripts and optional Jupyter notebooks.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync --all-extras
```

## Quality gates

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest -n auto --cov=blueberries_voi --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

Everyday loops can use plain `uv run pytest` (no coverage). See `AGENTS.md` for
the role gate ladder.

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
