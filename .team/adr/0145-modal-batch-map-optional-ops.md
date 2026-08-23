# ADR 0145: Modal batch map for notebook heavy jobs (optional ops)

**Status:** ACCEPTED (provisional)  
**Ticket:** T-155 (driver); T-150 uses this driver for notebook 13 closeout

`team/T-155/implement` was not merged wholesale — T-150 integrate cherry-picked the
audit spec and mypy stubs only; F3 grid, shard output, and conditional gsin mount
stay on the T-150 integrate line.

T-150 arrival physics remains **[ADR 0144](./0144-f-native-hierarchical-arrival-model.md)**. This ADR is the
optional Modal batch map only — it does not renumber or replace 0144.

## Context

Notebook 13 (filter-accuracy channel factorial) and the `gsin_upc_diag` harness each
spend most wall time on **independent** inner loops (distinct `(seed, channel)` or
`(regime, seed)` cells). Days within a seed stay sequential because belief carries
forward. CI and local dev must not require a Modal account.

## Decision

1. Extract job functions into importable modules under
   `src/blueberries_voi/experiments/`.
2. Provide a **local** `ProcessPoolExecutor` driver and a **Modal** `@app.function`
   + `starmap` driver under `experiments/modal/`.
3. Modal is an **optional** dev/ops extra (`[project.optional-dependencies] modal`);
   it is not a runtime dependency of the installable package.
4. Modal images install a **pre-built** `blueberries_voi` PyO3 wheel (`maturin build`)
   and copy the release `gsin_upc_diag` example binary — **no Rust compile on cold
   start**.
5. `gsin_upc_diag` gains a `--shard <regime_idx> <seed_idx>` mode so one truth episode
   is simulated per shard and all six observation masks are replayed cheaply.

## Alternatives rejected

- **nbconvert whole notebooks on Modal** — couples orchestration to notebook state;
  hides job grain; replays plotting cells.
- **Compile Rust on Modal image build via maturin in Dockerfile** — slow/unreliable
  cold starts; violates pre-built wheel requirement.
- **288 independent gsin jobs (regime × seed × channel)** — recomputes truth 6× per
  seed; rejected in favour of truth-once-per-(regime, seed).

## Consequences

- Operators build wheel + diag binary locally before `modal run`.
- CI tests job merge / grid construction and tiny `_core` smoke paths; no live Modal.
- `web/package.json` unchanged (no publishable studio paths).
