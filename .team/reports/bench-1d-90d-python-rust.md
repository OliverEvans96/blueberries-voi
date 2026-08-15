# 1-day vs 90-day EngineSession: Python vs Rust (release PyO3)

Informational, citeable-enough wall times for the **interactive studio path**.
Not a VOI paper table. RNG streams are independent PCG vs NumPy — **not
bit-identical**. Citeable VOI stays on Python.

Pyodide / WASM are **out of this report** (follow-on). Abdella parquet is **not**
on the timed path.

## Headline (mean of 3 timed repeats after 1 warmup)

Same fixture and demo budgets. **Simulator** = fixed order qty (no policy).
**Controller** = `act(policy="rollout")` on both backends (Rust `act` is
rollout-only).

| path | 1d python | 1d rust | 90d python | 90d rust |
| --- | ---: | ---: | ---: | ---: |
| **simulator** (`step` / batched `step_n`) | **23.8 ms** | **0.127 ms** | **10.9 s** | **23.9 ms** |
| **controller** (`act` rollout) | **126 ms** | **0.190 ms** | **67.4 s** | **1.47 s** |

90-day **simulator** is one `step_n([16]*90)` (one Rust FFI crossing).
90-day **controller** is **90× `act`** — there is no `act_n`; Rust records 90
FFI crossings plus init.

Approx. speedup (this machine): simulator ~190× / ~455× (1d / 90d);
controller ~660× / ~46× (1d / 90d). Controller 90d Python ranged 35–93 s
across the three repeats (inventory-dependent rollout).

### Simulator-only 2×2 (same cells as the first row)

| | **python** | **rust** (PyO3, **release**) |
| --- | ---: | ---: |
| **1 calendar day** (`step(16)`) | **23.8 ms** | **0.127 ms** |
| **90 calendar days** (one `step_n([16]*90)`) | **10.9 s** | **23.9 ms** |

## Method

- **SHA:** `3821260` (T-110 2×2 follow-on) plus this controller pass.
- **Python:** 3.11.13. **CPU:** Intel Core i7-8550U @ 1.80 GHz. **rustc:**
  1.93.0. Extension built with `maturin develop --release`.
- **Threads:** `OMP_NUM_THREADS=1` `OPENBLAS_NUM_THREADS=1`.
- **Fixture:** `smoke_cool_shipments()` (synthetic 1 °C cool; no Abdella parquet).
- **Budgets:** `n_particles=200`, `H=7`, `n_rollout_paths=2`,
  `candidate_case_radius=1`, `enable_filter=True` (`DEMO_BUDGETS`).
- **Simulator 1d:** `EngineSession.step(16)` after `init`.
- **Simulator 90d:** one `step_n([16] * 90)` — one host/FFI crossing on Rust.
- **Controller 1d:** `EngineSession.act(policy="rollout")`.
- **Controller 90d:** 90 Python-level `act(policy="rollout")` calls (no `act_n`).
- **Timing:** warmup discarded, then mean of 3 repeats. Each timed call does a
  fresh `init` then the work (init cost is inside the cell).
- Re-run: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run --python 3.11 python experiments/bench_1d_90d.py`
  (JSON under gitignored `outputs/bench_1d_90d_python_rust.json`).

## Footnote: 90 naive `step` calls

Same 90 physics days, but 90× `step(16)` instead of one `step_n`.

| | python | rust release |
| --- | ---: | ---: |
| 90× `step` | 10.0 s | 39.4 ms |

Filter N=200 dominates; FFI is not the 90-day simulator story.

## Physics-only (clarifies; not the headline)

`day_step` with injected demand, **no** RBPF. Rust still crosses PyO3 **once
per day** (no Python `advance_days` binding).

| | python | rust (per-day PyO3) |
| --- | ---: | ---: |
| 1 `day_step` | 0.58 ms | 0.33 ms |
| 90× `day_step` loop | 21.2 ms | 22.5 ms |

The EngineSession 90-day simulator gap is **filter + session**, not bare MOD-12
physics.

## Caveats

- Rust vs Python RNG is **not** bit-identical; do not treat times as a
  numerical-correctness check.
- Not Pyodide, not wasm, not production N=2000, not Abdella parquet.
- Debug PyO3 is **not** this table; this column is **release**.
- Init + filter bootstrap sit inside each timed cell.
- Controller 90d is **not** batched inside Rust; a future `act_n` would drop
  FFI from 90 to 1 but would not change the nested rollout work.
