# Intake 2026-08-12 — Initialize uv + agent-dev-team project

## Request (their words)
> Please initialize this project for uv + the agent dev team methodology. We will
> be doing some simulation, analysis and visualization in Python. We may have
> both package scripts and notebooks.

## What they want
A ready-to-work Python repository: reproducible env via uv, TDD/quality gates,
agent-dev-team state under `.team/`, and a layout that supports both installable
package/CLI scripts and Jupyter notebooks for simulation and analysis.

## In scope
- uv + `src/` package scaffold with lockfile
- Ruff, mypy strict, pytest + branch coverage
- `.team/` methodology skeleton and `AGENTS.md`
- Notebook directory and optional Jupyter extra
- Thin CLI entry point

## Out of scope
- Domain simulation models or analysis code
- Specific visualization stack choices (matplotlib vs others)
- Deployed services or data pipelines
- Nix flake (optional; not requested)

## Open questions
- [ ] Confirm package/project naming (`blueberries-voi` / `blueberries_voi`)
- [ ] Preferred first analysis/visualization libraries (e.g. numpy, pandas, matplotlib)
- [ ] Whether GitHub Actions CI should be added manually (workflow writes are guarded)

## Assumptions if unanswered
- Keep project/package names derived from the repo directory
- Leave runtime deps empty until an ADR per dependency
- Document CI template in README/AGENTS; do not fight the workflow guard
