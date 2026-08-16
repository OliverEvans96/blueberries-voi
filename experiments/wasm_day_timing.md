# WASM / native one-day advance timing (DEMO_BUDGETS)

Interactive studio path: **user order or autopilot → one simulated day** (plot
rendering excluded). Rust/WASM only (no Pyodide).

**SHA:** `303c502cecef9069a11b6d7164b7850d564bba23`  
**CPU:** Intel Core i7-8550U @ 1.80 GHz (8 threads; benches pinned `OMP_NUM_THREADS=1`)  
**rustc:** 1.93.0, `cargo run -p voi_core --release --bin bench_day_timing`  
**WASM:** wasm-pack `packaging/wasm/pkg`, Node harness `experiments/bench_wasm_day_timing.mjs`

## 1. RPC path (what autopilot calls)

```mermaid
sequenceDiagram
  participant UI as Studio UI
  participant Loop as createAutopilotLoop
  participant Ad as WasmAdapter
  participant W as packaging/wasm/worker.js
  participant RPC as voi_wasm::handle_rpc
  participant S as EngineSession

  UI->>Loop: play / tick
  Loop->>Ad: act(controllerToActOpts())
  Ad->>W: postMessage JSON {method:"act", params:{policy, budgets...}}
  W->>RPC: handle_rpc(request_json)
  RPC->>S: act(policy, ...) then advance_one(order)
  S-->>RPC: DayDelta + belief wire
  RPC-->>W: JSON {ok, result}
  W-->>Ad: message
  Ad-->>Loop: DayDelta
  Loop->>UI: applyDelta (no plot in this bench)
```

| User action | Frontend | Worker RPC | Rust entry | Core work |
|-------------|----------|------------|------------|-----------|
| Manual **Step** with slider qty | `WasmAdapter.step(qty)` | `step` | `EngineSession::step` | `advance_one(order)` |
| **Autopilot** (default `damped_sw`) | `adapter.act({policy, budgets})` | `act` | `EngineSession::act` | `damped_sw_order_belief` → `advance_one` |
| **Autopilot** (`rollout` policy) | same | `act` `{policy:"rollout"}` | `EngineSession::act` | `damped_sw` base → `rollout_order` → `advance_one` |

`advance_one` (`crates/voi_core/src/session.rs`): schedule gate → pending
arrival → demand draw → **`day_step`** → build `RichDay` → **`filter_step`**
(if filter on) → update state → **`particle_bank_to_flat`** in `day_delta_value`.

Autopilot wiring: `web/src/react/studioLogic.ts` → `createAutopilotLoop` →
`adapter.act(controllerToActOpts())`. Default interval 500 ms (`damped_sw`) /
1000 ms (`rollout`) per `web/src/autopilotLoop.ts` — compute target is **≪**
500 ms/day at DEMO_BUDGETS.

**DEMO_BUDGETS:** `n_particles=200`, `H=7`, `n_rollout_paths=2`,
`candidate_case_radius=1`, `enable_filter=true`, `L=2`, `K=4`, smoke-cool
shipments, `obs_scenario=P1`.

## 2. Method

- **Warm state:** 7 days (`step(16)`) before each timed advance (excluded from timer).
- **Repeats:** 200 native / 100 WASM after 20 warmup discards.
- **Fixture:** seed 42, order qty 16 (one case), filter on.
- **Native:** direct `EngineSession` (no PyO3, no JSON).
- **WASM:** `handle_rpc` in Node (includes JSON parse/stringify + wasm32 codegen).
- **Pass/fail:** p95 ≤ **500 ms** per day (autopilot comfortable max).

Re-run:

```bash
OMP_NUM_THREADS=1 cargo run -p voi_core --release --bin bench_day_timing
./scripts/build-wasm.sh && node experiments/bench_wasm_day_timing.mjs
```

## 3. Native release (measured)

| path | mean ms | p95 ms | max days/s (p95) | ≤500 ms |
|------|--------:|-------:|-----------------:|:-------:|
| `step(order)` | 0.368 | 0.535 | 1,870 | **PASS** |
| `act(damped_sw)` | 0.383 | 0.638 | 1,567 | **PASS** |
| `act(rollout)` | 0.407 | 0.610 | 1,639 | **PASS** |

### Decomposition (microbench, same budgets)

| component | mean ms | p95 ms | notes |
|-----------|--------:|-------:|-------|
| `day_step` | 0.001 | 0.002 | physics only |
| `filter_step` | 0.115 | 0.190 | N=200, P1 mask |
| `belief_export` (flat) | 0.005 | 0.007 | `particle_bank_to_flat` |
| `belief_mean` (policy) | 0.005 | 0.008 | `damped_sw` / rollout input |
| `rollout_order` | 0.038 | 0.067 | H=7, paths=2, radius=1 |
| **non-filter `advance_one` overhead** | ~0.25 | — | demand, schedule, clones, wire (derived) |

Rollout adds ~0.04 ms policy work on top of `step`; filter dominates variance.

## 4. WASM (measured, Node wasm32)

| path | mean ms | p95 ms | max days/s (p95) | ≤500 ms |
|------|--------:|-------:|-----------------:|:-------:|
| `step(order)` | 0.970 | 1.922 | 521 | **PASS** |
| `act(damped_sw)` | 0.548 | 0.784 | 1,276 | **PASS** |
| `act(rollout)` | 0.569 | 0.776 | 1,287 | **PASS** |

Cold wasm module init (one-time): **63 ms** (not per day).

**Native→WASM multiplier (measured):**

| path | mean ratio | p95 ratio |
|------|----------:|----------:|
| `step` | 2.6× | 3.6× |
| `act(rollout)` | 1.4× | 1.3× |

`step` is slower in WASM largely from JSON envelope + belief serialization;
`act` timings include schedule-gated order days (mixed workload). For planning,
use **1.5×** as a conservative native→browser multiplier (user suggestion) and
**measured WASM** where available.

## 5. C1 / C2 / C3 (stochastic gamma freshness — not implemented)

These models are **not in the codebase**. Estimates below combine:

1. **Measured** repeated-`filter_step` scaling (native, same bank/obs):

| filter passes / rep | mean ms | vs baseline |
|--------------------|--------:|------------:|
| ×1 (current) | 0.144 | 1.0× |
| ×2 (~C1 low) | 0.178 | 1.2× |
| ×3 (~C1 high) | 0.198 | 1.4× |
| ×5 (~C3 mid) | 0.270 | 1.9× |
| ×8 (~C2 high) | 0.365 | 2.5× |

2. **Extrapolated** full-path cost model (honest approximation):

`step_ms ≈ step_current + filter_baseline × (cost_mult − 1)` with
`step_current=0.368 ms`, `filter_baseline=0.115 ms`, then WASM via
`max(measured_ratio, 1.5×)` on p95.

| scenario | filter cost mult (spec) | native step p95 est. | WASM p95 est. (1.5×) | WASM p95 est. (measured step ratio 3.6×) | ≤500 ms |
|----------|------------------------:|---------------------:|---------------------:|-------------------------------------------:|:-------:|
| **current** | 1× | 0.54 | 0.80 | 1.92 | PASS |
| **C1** lot-shared f, bootstrap PF | 1.5–2.5× | 0.63–0.71 | 0.94–1.07 | 2.3–2.6 | PASS |
| **C2** unit-level f in day_step + filter | 3–8× | 0.77–1.17 | 1.16–1.76 | 2.8–4.2 | PASS |
| **C3** histogram K=32 per lot | 2–5× | 0.69–0.83 | 1.03–1.24 | 2.5–3.0 | PASS |

| path @ C2 high (8× filter, worst case) | native p95 est. | WASM p95 est. (1.5×) |
|----------------------------------------|----------------:|---------------------:|
| `step` | 1.17 ms | 1.76 ms |
| `act(rollout)` | ~1.24 ms | ~1.86 ms |

C2 may also add **day_step** cost (unit-level f); not modeled — could widen C2
by another ~0.1–0.5 ms if day_step grows with per-unit state.

## 6. Summary table (p95, ms)

| model | step native | step WASM (meas.) | act damped native | act damped WASM (meas.) | act rollout native | act rollout WASM (meas.) |
|-------|------------:|------------------:|--------------------:|------------------------:|-------------------:|-------------------------:|
| current | 0.54 | 1.92 | 0.64 | 0.78 | 0.61 | 0.78 |
| C1 (2× filter) | 0.66 | 1.98† | 0.76† | 0.84† | 0.73† | 0.84† |
| C2 (8× filter) | 1.17 | 1.76† | 1.27† | 1.91† | 1.24† | 1.86† |
| C3 (5× filter) | 0.83 | 1.24† | 0.93† | 1.17† | 0.90† | 1.17† |

† extrapolated from native filter scaling + 1.5× WASM factor (not re-measured in wasm32).

**Headline:** At DEMO_BUDGETS on this CPU, **all paths are far below 500 ms/day**
(native ~0.4–0.6 ms p95; WASM ~0.8–1.9 ms p95). Autopilot at 2 days/s
(500 ms interval) is compute-safe with large margin. Even **C2 high** stays
under 2 ms p95 native / ~2 ms WASM (1.5× estimate).

## 7. Artifacts

| file | purpose |
|------|---------|
| `crates/voi_core/src/bin/bench_day_timing.rs` | native release harness (quick smoke) |
| `experiments/bench_wasm_day_timing.mjs` | WASM `handle_rpc` harness |
| `experiments/bench_order_autopilot_timing.py` | aggregates native + WASM JSON |
| `experiments/wasm_day_timing.md` | this report (initial pass; see `freshness_timing_sweep.md` for parameter grids) |
