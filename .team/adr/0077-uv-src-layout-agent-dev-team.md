# 0077. uv + src layout + agent-dev-team for simulation work

STATUS: ACCEPTED
DATE: 2026-08-12
NOTE: Renumbered from 0001 on import of Afresh domain ADRs 0001–0076.

## Context
The repo starts empty. Work will mix simulation, analysis, visualization,
installable scripts, and notebooks. We need a reproducible Python toolchain and
a place for team process state before any domain code lands.

## Decision
- Use **uv** with a committed `uv.lock` and editable `src/blueberries_voi` package.
- Enforce **Ruff**, **mypy strict**, and **pytest** with ≥80% branch coverage.
- Put exploration in `notebooks/` behind an optional `[notebooks]` extra;
  promote shared logic into the package with tests.
- Follow **agent-dev-team**: facts in `.team/`, roles done when their files exist.
- Keep a thin CLI (`blueberries-voi` / `python -m blueberries_voi`).

## Alternatives considered
- Flat scripts-only repo — rejected because reuse and testing become hard once
  notebooks and CLIs share logic.
- Poetry/Pipenv — rejected; uv is the chosen local toolchain.
- Notebooks as the only surface — rejected; untested notebook-only logic drifts.

## Consequences
- New runtime dependencies need an ADR before landing.
- CI workflow files are protocol-guarded; humans must add/change
  `.github/workflows/` if desired.
- Domain libraries (numpy, plotting, etc.) are intentionally not pre-installed.
