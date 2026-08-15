# 1-day vs 90-day EngineSession: Python vs Rust vs Pyodide

Informational, citeable-enough wall times for the **interactive studio path**.
Not a VOI paper table. RNG streams are independent PCG vs NumPy — **not
bit-identical**. Citeable VOI stays on Python.

## Headline (mean of 3 timed repeats after 1 warmup)

Same fixture and demo budgets. **Simulator** = fixed order qty (no policy).
**Controller** = `act(policy="rollout")` (Rust `act` is rollout-only).

| path | 1d python | 1d rust | 1d pyodide | 90d python | 90d rust | 90d pyodide |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **simulator** (`step` / batched `step_n`) | **23.8 ms** | **0.127 ms** | **73.1 ms** | **10.9 s** | **23.9 ms** | **23.1 s** |
| **controller** (`act` rollout) | **126 ms** | **0.190 ms** | **209 ms** | **67.4 s** | **1.47 s** | **81.8 s** |

90-day **simulator** is one `step_n([16]*90)` (one Rust FFI crossing; one
Pyodide RPC). 90-day **controller** is **90× `act`** — there is no `act_n`.

Pyodide **cold start** (`loadPyodide` + slim wheel + packages): **27.2 s**,
**not** folded into the 1-day cells.

### Compact layout (same numbers)

| path | 1d python | 1d rust | 90d python | 90d rust |
| --- | ---: | ---: | ---: | ---: |
| **simulator** | 23.8 ms | 0.127 ms | 10.9 s | 23.9 ms |
| **controller** | 126 ms | 0.190 ms | 67.4 s | 1.47 s |

| path | 1d pyodide (Node, 314.0.4) | 90d pyodide |
| --- | ---: | ---: |
| **simulator** | 73.1 ms | 23.1 s |
| **controller** | 209 ms | 81.8 s |

## Method

- **Branch / SHA:** `team/T-110/bench-1d-90d` (python/rust at `dceacf5`; this
  Pyodide pass on top).
- **Python native:** 3.11.13. **CPU:** Intel Core i7-8550U @ 1.80 GHz.
  **rustc:** 1.93.0, `maturin develop --release`.
- **Pyodide:** 314.0.4 via npm `loadPyodide` in Node (not the studio Vite
  server on 5173). Slim wheel from `scripts/build_slim_wheel.py`. Same worker
  RPC as `packaging/pyodide/worker.js` (`init` / `step` / `step_n` / `act`).
- **Threads (native):** `OMP_NUM_THREADS=1` `OPENBLAS_NUM_THREADS=1`.
- **Fixture:** `smoke_cool_shipments()` / `ensure_demo_shipments` (no Abdella
  traces as the **session** shipment list). Native and Pyodide filter birth
  priors still read vendored Abdella parquet on first delivery (CPython from
  the checkout; Pyodide from files mounted into the emscripten FS — same
  files, not invented traces).
- **Budgets:** `n_particles=200`, `H=7`, `n_rollout_paths=2`,
  `candidate_case_radius=1`, `enable_filter=True` (`DEMO_BUDGETS`).
- **Simulator 1d:** `step(16)` after `init`.
- **Simulator 90d:** one `step_n([16] * 90)`.
- **Controller 1d:** `act(policy="rollout")`.
- **Controller 90d:** 90× `act(policy="rollout")` (no `act_n`).
- **Timing:** warmup discarded, then mean of 3 repeats. Fresh `init` inside
  each cell. Pyodide cold start timed separately.
- Re-run native:
  `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run --python 3.11 python experiments/bench_1d_90d.py`
- Re-run Pyodide:
  `uv run python scripts/build_slim_wheel.py && NODE_PATH=… node --max-old-space-size=8192 experiments/bench_1d_90d_pyodide.mjs`
  (JSON under gitignored `outputs/`).

## Footnote: 90 naive `step` (native only)

| | python | rust release |
| --- | ---: | ---: |
| 90× `step` | 10.0 s | 39.4 ms |

Filter N=200 dominates; FFI is not the 90-day simulator story.

## Physics-only (native; not the headline)

| | python | rust (per-day PyO3) |
| --- | ---: | ---: |
| 1 `day_step` | 0.58 ms | 0.33 ms |
| 90× `day_step` loop | 21.2 ms | 22.5 ms |

## Caveats

- Rust vs Python RNG is **not** bit-identical.
- Not wasm-pack, not production N=2000. Session shipments are smoke-cool, not
  Abdella temperature paths.
- Debug PyO3 is **not** the rust column; that column is **release**.
- Init sits inside each timed cell; Pyodide `loadPyodide` does not.
- Controller 90d is **not** batched; Pyodide 90d act mean 81.8 s (range
  70–89 s) finished well under 40 min, so no 7/14-day n/a footnote.
- Pyodide 90d simulator ranged 16–37 s across repeats.
