# 0084. Add numpy, scipy, and matplotlib as M1 runtime dependencies

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: *(repo)*
GROUP: ENG
PROVENANCE: M1 implementation plan
TIER: 2
MILESTONE: M1 — filter recovers truth from synthetic P1 data

## Context

ADR 0077 left runtime scientific dependencies empty pending a justifying ADR. M1 needs array
numerics (arrival-age integrals, Weibull survival ratios, particle weights), distribution primitives
(negative binomial, binomial), and static committed figures (ENG-03=A / X-10). Notebooks remain an
optional extra; figure **generation** for the reproducibility pipeline must live in the installable
package / `experiments/` scripts, not only in ad-hoc notebooks.

## Decision

We will add **numpy**, **scipy**, and **matplotlib** as **runtime** dependencies of
`blueberries_voi` (declared in `pyproject.toml`, locked via `uv.lock`) for M1 simulation, filter
bakeoff, and figure commits.

## Alternatives considered

- **Pure-Python numerics only** — rejected: too slow and error-prone for grids, particles, and
  survival math under mypy-strict typed code; reinventing NB/binomial RNGs poorly.
- **Notebook-only plotting (matplotlib only in `[notebooks]` extra)** — rejected: ENG-03/X-10 require
  scripted, committed static figures; plotting helpers belong in `viz/` importable by experiments.
- **plotly / JS embeds for M1 figures** — rejected: ENG-03=A chose static matplotlib images.
- **pandas as a runtime dep for M1** — not chosen here; add only if a later ADR shows tabular I/O
  needs that numpy cannot cover.

## Consequences

- `uv sync` pulls numpy/scipy/matplotlib for all installs; CI/typecheck must see their stubs or
  typed usage as elsewhere in the toolchain.
- Package code may import these three freely; new runtime libs still need their own ADR.
- Cost: larger env and lockfile; acceptable for a simulation/analysis package.
- Aligns with X-09=B (Python throughout) and ENG-02 layout (`viz/` for matplotlib helpers).

**Depends on:** `0077`, `ENG-02`, `ENG-03`, `X-09`, `X-10`

**Milestone:** M1 — filter recovers truth from synthetic P1 data
