# 0127. Tier 2 Rust compute kernel — sole hot path; Python orchestration only

STATUS: ACCEPTED
DATE: 2026-08-15
ACCEPTED: 2026-08-15
BOARD-ID: X-09
GROUP: X
PROVENANCE: Rust compute parity plan (2026-08-15); milestone T-121
TIER: 2
AMENDS: 0119

## Context

ADR [0119](./0119-rust-compute-kernel-python-host.md) introduced `crates/voi_core` as a
shared compute kernel while keeping **duplicate Python hot loops** and defaulting
`BLUEBERRIES_VOI_BACKEND=python` until golden parity landed. Studio benches show
Pyodide running the same session logic ~10–100× slower than native Rust; WASM
`handle_rpc` still uses thin init defaults (16 particles, smoke shipments) while
Python `EngineSession` exposes full configure, belief wire, policy dispatch, calendar
demand (CAL-01), and VOI observation masks.

The browser adapter contract (`init`, `reset`, `step`, `step_n`, `act`,
`set_obs_scenario`) requires one day loop — physics → filter → policy → belief wire —
entirely in Rust/WASM. Batch VOI (`run_voi_crn_cell`) repeats the same kernels for
seven scenarios × burn/score days; PyO3 already exposes `run_voi_crn_cell_py` but gaps
are wire fidelity, belief-based `act`, calendar demand, and VOI masks — not missing
architecture.

**Tier 2 locked (2026-08-15):** one source of truth for all **hot** compute in
`voi_core`; Python becomes thin FFI + orchestration (sweep loops, bootstrap CI, viz,
Abdella parquet → JSON, alpha-table loading, FastAPI glue). Tier 3 (port sweep to
Rust) is explicitly out of scope — orchestration cost is negligible vs CRN cells.

Structural RNG parity is acceptable: Rust PCG matches NumPy PCG64 *family*, not
bit-identical streams (per 0119). Policy parity tests compare **order quantities** and
scenario differentiation under tolerance, not identical belief histograms (Rust
`particle_bank_to_flat` vs Python `shelf_belief_from_rbpf` semantics differ).

ADR [0118](./0118-behavior-frozen-module-splits.md) case-rounding owners remain frozen:
session driver **ceil** vs SW policy **nearest** — do not unify in T-121.

## Decision

1. **`crates/voi_core` is the sole hot compute kernel** for interactive session
   (WASM RPC + PyO3) and batch VOI (`run_voi_crn_cell`). Physics, filter, policies,
   calendar demand, and VOI episode loops live in Rust only after Wave E verify.
2. **Python remains the host** for notebooks, CLI, FastAPI, Abdella I/O, viz, sweep
   orchestration (`voi/sweep.py`), and bootstrap CI — not a second implementation of
   physics, filter, session advance, or VOI CRN episodes.
3. **Thin Python façades** after Wave F:
   - `simulator/session.py` → PyO3 dispatch + wire coercion shims (no Python
     `_advance` physics).
   - `voi/crn.py` → Abdella load when `shipments=None`, alpha table, then
     `run_voi_crn_cell_py`.
   - `backend.py` → default `BLUEBERRIES_VOI_BACKEND=rust`; warn if extension missing.
4. **Amends ADR 0119 §Decision items 1 and 3:** Rust becomes the **production compute**
   path once T-121 Wave E verify is green; default backend flips to `rust`. Citeable
   VOI numbers may differ in last bits (structural RNG); document in reports, do not
   claim bit-identical CRN vs NumPy.
5. **Modules safe to delete in Wave F** (after Wave E PASS — not before):
   - `model/physics.py`, `model/day_step.py` compute paths
   - `filter/rbpf.py`, `filter/particle/counts_update.py` production path
   - `controller/damped_sw.py`, `controller/rollout.py`, `controller/ordering.py`
   - `simulator/day_driver.py`
   - Python body of `voi/crn.py` (episode loop only; keep Abdella/alpha orchestration)
   Keep types, protocols, and re-export façades needed by viz, bakeoff diagnostics, and
   `BLUEBERRIES_VOI_BACKEND=python` fallback until a later ADR retires it.
6. **Browser path unchanged from 0119:** no PyO3 for Pyodide (`wasm32-unknown-emscripten`);
   WASM bindgen only. Long-term Pyodide compute worker retirement is a human decision
   documented here, not blocking Wave F.
7. **Implementation concurrency:** `crates/voi_core/src/session.rs` has **one writer at
   a time** (A2 → B3 → C3 serial on session-owner). `voi.rs` serial C4 → D1.
   `voi_py/src/lib.rs` serial A1 → B4. See `.team/specs/T-121.md` merge order.
8. **Verification:** each wave ends with CI-parity on Python 3.11 plus
   `cargo test -p voi_core -p voi_wasm`.

## Alternatives considered

- **Tier 1 — browser-only Rust** — rejected: leaves full Python session + VOI forever;
  worst duplicate-code outcome; Pyodide stays slow.
- **Tier 3 — port sweep/bootstrap to Rust** — rejected: low payoff; research
  orchestration stays readable in Python.
- **Keep 0119 dual implementation indefinitely** — rejected: maintenance burden and
  bench gap; Tier 2 is the agreed stop before Tier 3.
- **Bit-identical NumPy RNG in Rust** — rejected: NumPy Generator/SeedSequence is not a
  public bit-stable contract (0119).
- **Unify ceil vs nearest case rounding during port** — rejected: violates 0118 frozen
  semantics.

## Consequences

**Easy:** WASM and PyO3 share identical kernels; one parity test suite; Wave F shrinks
Python LOC to orchestration; browser prod path unblocked after Wave A.

**Hard:** Large coordinated milestone (T-121) with file-ownership rules; qa RED tracks
run in parallel but session.rs changes serialize; Wave F requires updating tests that
import deleted modules (`test_damped_sw_policy.py`, `test_rollout.py`, `test_t097_*`,
`test_voi_crn.py`, bakeoff backends) in the same ticket — not left for verifier FAIL.

**Locked in:** Tier 2 scope; structural RNG; default `rust` after Wave E; listed modules
deletable in Wave F; 0119 items on “keep all Python bodies” and “default python”
superseded for hot compute paths only.

**Still binding from 0119:** Python host for orchestration; no emscripten PyO3; no
`*wasm*` Python packages under `src/blueberries_voi`; golden tests use tight `atol` on
deterministic kernels and moment/histogram checks on stochastic paths.
