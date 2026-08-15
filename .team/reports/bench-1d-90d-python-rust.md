# 1-day vs 90-day EngineSession: Python vs Rust (release PyO3)

Informational, citeable-enough wall times for the **interactive studio path**.
Not a VOI paper table. RNG streams are independent PCG vs NumPy — **not
bit-identical**. Citeable VOI stays on Python.

Pyodide / WASM are **out of this report** (follow-on). Abdella parquet is **not**
on the timed path.

## Headline 2×2 (mean of 3 timed repeats after 1 warmup)

Same fixture, same budgets, filter on, fixed order qty (not `act` / rollout).

| | **python** | **rust** (PyO3, `BLUEBERRIES_VOI_BACKEND=rust`, **release**) |
| --- | ---: | ---: |
| **1 calendar day** (`step(16)`) | **32.0 ms** | **0.207 ms** |
| **90 calendar days** (one `step_n([16]*90)`) | **14.9 s** | **34.4 ms** |

Approx. speedup (this machine): ~155× for one day, ~430× for 90 batched days.

## Method

- **SHA:** `68bbc15` (T-110 implement/verify tip) plus this follow-on (N=200
  passed into Rust `EngineSession.configure`; previously Rust stayed at N=16).
- **Python:** 3.11.13. **CPU:** Intel Core i7-8550U @ 1.80 GHz. **rustc:**
  1.93.0. Extension built with `maturin develop --release`.
- **Threads:** `OMP_NUM_THREADS=1` `OPENBLAS_NUM_THREADS=1`.
- **Fixture:** `smoke_cool_shipments()` (synthetic 1 °C cool; no Abdella parquet).
- **Budgets:** interactive demo — `n_particles=200`, `H=7`, `n_rollout_paths=2`,
  `candidate_case_radius=1`, `enable_filter=True` (same as studio `DEMO_BUDGETS`).
- **Day:** `EngineSession.step(16)` after `init` (fixed order; controller nest
  does not dominate).
- **90 days:** one `step_n([16] * 90)` — **one** host/FFI crossing on Rust
  (`host_crossings` +1), not 90 Python-level loops that each cross FFI.
- **Timing:** warmup discarded, then mean of 3 repeats. Each timed call does a
  fresh `init` then the step / `step_n` (init cost is inside the cell).
- Re-run: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run --python 3.11 python experiments/bench_1d_90d.py`
  (JSON under gitignored `outputs/bench_1d_90d_python_rust.json`).

## Footnote: 90 naive `step` calls

Same 90 physics days, but 90× `step(16)` instead of one `step_n`.

| | python | rust release |
| --- | ---: | ---: |
| 90× `step` | 12.4 s | 32.9 ms |

On this machine the naive loop is in the same ballpark as batched `step_n`
because **filter N=200 dominates**; FFI is not the 90-day story. Headline
90-day cells remain the batched `step_n`.

## Physics-only (clarifies; not the headline)

`day_step` with injected demand, **no** RBPF. Rust still crosses PyO3 **once
per day** (no Python `advance_days` binding).

| | python | rust (per-day PyO3) |
| --- | ---: | ---: |
| 1 `day_step` | 0.50 ms | 0.14 ms |
| 90× `day_step` loop | 16.2 ms | 18.1 ms |

The EngineSession 90-day gap (14.9 s vs 34 ms) is **filter + session**, not
bare MOD-12 physics.

## Caveats

- Rust vs Python RNG is **not** bit-identical; do not treat times as a
  numerical-correctness check.
- Not Pyodide, not wasm, not production N=2000, not Abdella parquet.
- Debug PyO3 (~8 ms smoke in an earlier T-109 note) is **not** this table;
  this column is **release**.
- Init + filter bootstrap sit inside each timed cell; cold `maturin` import is
  not folded in.
- `act` / rollout is **not** in the headline (would nest the controller).
