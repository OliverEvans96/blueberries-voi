# 0119. Rust compute kernel; Python remains host and citeable path

STATUS: ACCEPTED
DATE: 2026-08-14
BOARD-ID: X-09
GROUP: X
PROVENANCE: Oliver reopen (Rust WASM PyO3 plan)
TIER: 1
AMENDS: 0009

## Context

ADR [0009](./0009-x-09-language-and-stack.md) locked **Python throughout, JS for the browser sim**,
against the card’s Julia recommendation. Its revisit clause already contemplated sharing model
code with the browser. Interactive `EngineSession.act(rollout)` and nested VOI rollouts are now
Python-bounded (filter N=200 plus sequential-WOR DP plus nested `day_step`). Oliver explicitly
reopened the language decision for a **shared Rust compute kernel** exposed to CPython (PyO3)
and to the studio (`wasm32-unknown-unknown` + wasm-bindgen). Citeable VOI numbers must not
silently switch RNG families: Rust PCG is the same *family* as NumPy PCG64, **not** bit-identical.

ADR [0074](./0074-sim-filter-shared-day-step.md) still holds: sim and filter share one `day_step`.
That kernel lives in Rust `voi_core`; Python implementations stay in-tree.

## Decision

1. **Python remains the host** (notebooks, CLI, FastAPI, Abdella I/O, viz, sweep orchestration)
   and the **citeable VOI path** until a later ADR accepts Rust RNG as production.
2. **Rust `crates/voi_core` is the compute kernel** (physics, sequential-WOR DP, day/episode
   loops, RBPF counts-only, EngineSession). One crate; no second physics copy for the browser.
3. **Do not delete** existing Python modules. Opt-in `BLUEBERRIES_VOI_BACKEND=python|rust`
   (default `python` until golden tests and benches land).
4. **Do not** compile PyO3 for Pyodide (`wasm32-unknown-emscripten`). Browser path is
   wasm-bindgen only.
5. **No `*wasm*` / `*pyodide*` Python packages under `src/blueberries_voi`.** Rust sources live
   under `crates/`; WASM worker under `packaging/wasm/` and `web/`. This **supersedes** the T-047
   reading of “no wasm anywhere” with “no wasm **Python packages** under src.”
6. Golden tests: deterministic kernels match Python to tight `atol`; stochastic paths match
   moments/histograms, not bits. Independent PCG streams keyed like `spawn_rng`.

## Alternatives considered

- **Keep 0009 Python-only compute** — rejected: Oliver reopened; interactive and VOI nested
  loops are Python-bounded despite NumPy DP.
- **Julia core (0009 option A/C)** — rejected: the live library, tests, and studio already
  target Python; a third language would not share the PyO3/wasm-bindgen path.
- **Numba/Cython in-place** — rejected: does not give a browser kernel without Pyodide.
- **Bit-identical CRN vs NumPy** — rejected: NumPy Generator/SeedSequence is not a public
  bit-stable contract across a Rust port.

## Consequences

**Easy:** one kernel for CPython and the tab; batch FFI (`run_voi_crn_cell`, `step_n`) avoids
per-particle chatter; Python stays readable for the post.

**Hard / cost:** two implementations until Python is retired from hot loops; rustc required on
verify machines (human CI workflow copy); citeable numbers stay on Python until RNG ADR.

**Locked in:** Python host + citeable; Rust kernel; keep Python bodies; no emscripten PyO3.

**Supersedes in part:** [0009](./0009-x-09-language-and-stack.md) (compute language only; Python
host remains).
