# 0097. Add pytest-xdist for verify/CI full-suite runs

STATUS: ACCEPTED
DATE: 2026-08-12
BOARD-ID: *(repo)*
GROUP: ENG
PROVENANCE: agent gate-ladder / test-efficiency
TIER: 2
MILESTONE: process — role gate ladder

## Context

Full-suite verify and CI already run branch coverage with a ≥80% fail-under gate. As the suite
grows (filter bakeoffs, controller ladder, VOI smokes), wall-clock time on a single pytest worker
slows agent handoffs and PR feedback. Parallel workers are a standard pytest extension and do not
change which tests run or the coverage threshold — only how the suite is scheduled. Everyday agent
loops (qa RED, implement red/green) should stay fast and usually omit coverage; only verify/CI need
the expensive full command.

## Decision

We will add **pytest-xdist** as a **dev** optional dependency and run the verify/CI full suite with
`-n auto` (or equivalent) together with explicit coverage flags. Default `pytest` / `addopts` will
not enable coverage or xdist; those remain verify/CI-only.

## Alternatives considered

- **Stay single-process for verify/CI** — rejected: wall-clock cost grows with suite size and
  burns agent/CI minutes without improving the quality bar.
- **Custom multiprocessing / manual sharding in the workflow** — rejected: duplicates what xdist
  already provides; harder to run the same command locally for verify.
- **Make xdist / coverage the default `addopts`** — rejected: slows qa and implement red/green
  loops; coverage and parallelism belong on the verify/CI ladder rung only.

## Consequences

**Easy:** Verify and CI finish faster on multi-core runners without relaxing ruff, mypy, or the
≥80% coverage gate.  
**Hard:** Flaky or order-dependent tests surface under parallel collection; authors must keep tests
isolated (no shared mutable temp files without unique paths).  
**Locked:** `pytest-xdist` is a declared `[dev]` dependency; verify/CI document the full command
including `-n auto` and coverage flags.  
**Revisit if:** Parallelism causes systemic flakes that cost more than the wall-clock savings — then
narrow `-n` or pin serial markers for specific modules without dropping the coverage threshold.
