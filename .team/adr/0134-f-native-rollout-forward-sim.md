# 0134. F-native rollout forward sim supersedes `rollout.rs` scaffold

STATUS: PROPOSED
DATE: 2026-08-17
BOARD-ID: CTL-02 / CTL-04 / ENG
GROUP: CTL
PROVENANCE: T-131 — f-native rollout forward-sim parity (Rust primary)
TIER: 1
AMENDS: [0130](./0130-f-native-c2-a-unit-pf.md) §4 (rollout mechanics)
RELATED: [0059](./0059-ctl-02-depth-of-policy-improvement.md) (CTL-02=B single-step),
[0061](./0061-ctl-04-rollout-horizon-and-terminal-value.md) (CTL-04=B H + terminal salvage),
[0127](./0127-tier2-rust-compute-kernel.md) (Rust sole hot path),
[0112](./0112-x-11-mwf-delivery-base-case.md) (order schedule / pipeline)
SUPERSEDES (implementation): provisional `path_value_f_belief` scaffold in
`crates/voi_core/src/rollout.rs` (repeat-delivery bug, fixed demand, hard-coded costs,
no pipeline / schedule / base-policy continuation)

## Context

ADR **0059** (CTL-02=B) and **0061** (CTL-04=B) ratified one-step rollout with horizon
`H` and survival-weighted terminal salvage. Python reference logic lives in
`src/blueberries_voi/sim/bakeoff_rollout.py` (cohort `day_step`, Weibull `w_long`,
pipeline, `OrderSchedule`, base-policy continuation, paired CRN across candidates).

ADR **0130** moved production physics, filter, and policy to **f-native** `unit_day_step`
with belief wire `lot_counts` / `f_marginals` / `f_grid`. `EngineSession::act`,
`run_voi_crn_cell`, and `run_alpha_tune_episode` already call `rollout_order` in Rust,
but `path_value_f_belief` is still a **scaffold**:

- Re-delivers `first_order` on every day when `first_order > 0` (`deliver: d == 0 ||
  first_order > 0`).
- Uses fixed mean demand instead of `draw_demand` / `SpawnRng` demand stream.
- Hard-codes profit costs (`2.0`, `1.5`, `3.0`) and terminal margin.
- Ignores `OrderSchedule`, lead-time pipeline, and base `damped_sw_order_f_belief`
  continuation after day 0.
- Rebuilds terminal belief from path state with a nearest-bin hack instead of the
  documented salvage formula.

`alpha_tune.rs` already implements the correct **f-native closed-loop day kernel**
(pending queue, schedule-gated orders, stochastic demand, arrival metadata,
`truth_f_belief` for oracle belief). Rollout inner loops must share that kernel, not
re-invent a partial copy.

Orchestrator lock: **Rust primary** for rollout compute; Python is a **thin fallback**
when `blueberries_voi._core` is not built (notebooks / editable install without maturin).

T-030 acceptance tests for Python `controller/rollout.py` are module-skipped under
T-121 Wave F (`tests/test_rollout.py`). This ticket **supersedes** T-030 rollout
*compute* contracts for the f-native / Rust-primary era while preserving the same
observable gates (CRN pairing, ≥ base SW, salvage, desync detector).

## Decision

1. **Replace the scaffold** with an f-native forward simulator in
   `crates/voi_core/src/rollout.rs` that matches the structural contract of
   `bakeoff_rollout._path_value` / `alpha_tune` day stepping, adapted to unit-f state.

2. **Inner-loop contract** (rollout path evaluation only — no `filter_step` / `filter_step_unit`):
   - Initialize unit state from starting f-belief via `unit_state_from_f_belief` (existing helper).
   - Maintain `pending: BTreeMap<day, qty>`, `OrderSchedule`, `lead_time`, and `shipments`.
   - For sim day `h = 0..H-1` at calendar day `day0 + h`:
     - **Order:** `first_order` on `h == 0`; else `damped_sw_order_f_belief` on belief from
       **`truth_f_belief(freshness, lot_offsets, k)`** (oracle continuation — same as
       `alpha_tune` B-state scoring). Do **not** call the particle filter inside the rollout.
     - **Pipeline:** `enqueue` → `pop_arrival` on the lead-time map; deliver **only** when
       `arrival > 0` (never repeat `first_order`).
     - **Physics:** `unit_day_step` with `draw_demand` / `SpawnRng` streams
       (`:demand`, `:spoil`, `:alloc`, `:arrival_ship`, `:arrival_sensor`) addressed by
       `(root_seed, run_id|rollout|p{path}, day)` so candidates share CRN per path/day
       (ADR 0059 / SIM-05).
     - **Profit:** `day_profit` with caller-supplied `RolloutCosts` (not literals).
   - **Terminal:** `terminal_salvage_f_belief` at horizon end (see §3).

3. **Terminal salvage (ADR 0061 in f coordinates):** Under ADR 0130 the hot path has no
   Weibull. The f-native salvage weight per lot is **`w_long = E[f | lot]`** from
   `f_marginals × f_grid` (equivalently: sum of alive unit `f` values). Terminal value is

   ```text
   V_T = m * effective_inventory_f_belief(lot_counts, f_marginals, f_grid, pending_sum=0)
   ```

   i.e. margin × f-weighted on-hand with **zero pipeline** at `H`. `terminal_salvage_f_belief`
   remains the exported helper; implementation must use this formula on
   `truth_f_belief` at path end, not hard-coded margin or cohort τ / Weibull.

4. **`RolloutContext` API** (Rust, public to `session` / `voi` / `alpha_tune` / PyO3):

   ```rust
   pub struct RolloutCosts {
       pub margin: f64,
       pub waste_cost: f64,
       pub stockout_penalty: f64,
   }

   pub struct RolloutContext<'a> {
       pub lot_counts: &'a [f64],
       pub f_marginals: &'a [f64],
       pub f_grid: &'a [f64],
       pub params: &'a ModelParams,
       pub costs: RolloutCosts,
       pub schedule: &'a OrderSchedule,
       pub shipments: &'a [ShipmentTrace],
       pub pending0: &'a BTreeMap<u32, u32>,
       pub day0: u32,
       pub lead_time: u32,
       pub alpha: f64,
       pub rho: f64,
       pub f_pipeline_default: f64,
       pub root_seed: u64,
       pub run_id: &'a str,
   }
   ```

   - `path_value_f_belief(ctx, first_order, path, h) -> f64`
   - `rollout_order(ctx, base_q, h, n_paths, radius) -> Result<u32, String>`
   - Existing `rollout_order(lot_counts, …)` positional signature may remain as a thin
     wrapper with `RolloutCosts::default()` and `OrderSchedule::default()` for callers
     not yet threaded; **session / voi / alpha_tune must pass full context** (costs,
     schedule, pending, day, alpha, rho, shipments).

5. **Rust primary / Python fallback:**
   - Hot path: `rollout_order` in `voi_core` only (WASM `act`, PyO3, VOI CRN, alpha tune).
   - Python: when `rust_available()`, delegate via existing PyO3 / session backend; when
     `_core` is missing, **thin** re-export to `sim.bakeoff_rollout.rollout_order` (cohort
     reference kernel) with `warn_fallback_once` — no second Rust-quality reimplementation
     in Python.
   - `detect_crn_desync` stays in `bakeoff_rollout.py`; Rust rollout tests import it for
     the desync gate (ENG-04 prep).

6. **Guard supersession (same ticket):** qa must **replace** the module-level skip in
   `tests/test_rollout.py` (`T-121 F3: Python rollout compute removed`) with
   `tests/test_t131_f_native_rollout.py` (or equivalent) that asserts Rust f-native
   contracts. Preserve `tests/test_t083_baselines_rollout_m2.py` docstring / horizon
   constant checks against `bakeoff_rollout` exports (unchanged). Update
   `tests/test_rust_act_policies.py` rollout belief-parity xfails only when this ticket's
   AC are met (remove xfail or narrow reason).

7. **No new runtime dependencies.**

## Alternatives considered

- **Keep scaffold and only fix repeat-delivery** — rejected: leaves fixed demand, wrong
  terminal, and missing schedule/pipeline; VOI and alpha-tune scores stay biased.
- **Call `filter_step_unit` inside rollout paths** — rejected: CTL-02 forward sim evaluates
  the base policy under **known** continuation; filtering inside the inner loop double-counts
  observation noise and breaks oracle / alpha-tune parity. Belief updates use
  `truth_f_belief` on simulated unit state (same as B-state column).
- **Port `bakeoff_rollout` cohort logic to Rust verbatim** — rejected: contradicts ADR 0130
  f-native production path; duplicates τ / Weibull physics removed from the hot path.
- **Full Python reimplementation for parity** — rejected per ADR 0127; cohort fallback only
  when extension missing.
- **Weibull `w_long(τ)` on f-native rollout** — rejected: reintroduces retired hot-path
  survival; f-weighted salvage is the 0130 reading of ADR 0061.

## Consequences

**Easy:** One rollout kernel shared by studio `act`, VOI CRN, and alpha-tune; inner loop
reuses `alpha_tune` enqueue / demand / `unit_day_step` patterns; terminal salvage aligns
with `effective_inventory_f_belief`; T-030 observable gates transfer to Rust tests.

**Hard / cost:** `rollout_order` signature grows (context struct); all three Rust callers
must thread schedule, pending, costs, and CRN run_id; Python cohort fallback will not
match f-native Rust numerically when `_core` is absent (documented; structural only).
PyO3 `rollout_order_py` must accept costs or use documented defaults matching
`AlphaTuneCosts` / `ProfitCosts`.

**Locked in:** Oracle `truth_f_belief` continuation in rollout inner loop; no
`filter_step` in forward sim; f-native `V_T`; `RolloutContext`; Rust-primary dispatch.

**Revisit if:** Product requires particle-filter rollouts (CTL-02=C / deeper PI) or
bit-identical Python/Rust CRN — both need new ADR + bench evidence.

**Depends on:** ADR 0059, 0061, 0130; spec [T-030](../specs/T-030.md) (superseded compute,
preserved gates); spec [T-131](../specs/T-131.md).
