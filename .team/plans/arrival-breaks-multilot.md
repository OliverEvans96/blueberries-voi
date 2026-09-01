<!--
As-approved implementation plan, copied verbatim from the planning session
(2026-08-26) so it survives outside that session's scratch directory.

*** THERMAL / DURATION MODEL SUPERSEDED FOR IMPLEMENTATION ***

As of 2026-08-26 (PR #65 follow-up), §1 "Cold-chain breaks…" baseline
(deterministic fixed leg shares/setpoints only) is NO LONGER the authority for
Stage 1 implementation. Implement against:

  .team/plans/arrival-transit-generative-v2.md

That document keeps compound-Poisson breaks + generative traces + filter
caching, and adds: bottom-up Abdella-matched stage durations, trip thermal
modes, required hourly OU on charts, unified duration (no haul toggle), and
an explicit closed-form filter projection + Abdella calibration recipe.

This file remains authority for §2 multi-lot / §3 UPC-vs-LGTIN / remaining
non-thermal sections, unless a later plan says otherwise.

READ ALSO .team/handoffs/arrival-breaks-multilot.md (build state + corrections).

Historical corrections that led here:
  1. The calibration guard "98.4% duration share at rho->0" is UNACHIEVABLE
     under a fully deterministic legged baseline (100% share). v2 restores
     mild clean-chain φ̄ scatter via modes/OU and guards Var(log d) + φ̄ moments.
  2. ADR 0148 truncated-normal temp fit is retired; duration moment match stays.
  3. ADR numbers: 0149 (lots), 0150 (breaks) — amend 0150 baseline when
     implementing v2.
-->

# Multi-lot deliveries + cold-chain break events

## Context

Two observation channels in the knowledge ladder currently buy almost nothing, and in
both cases the cause is a modelling gap rather than a genuine finding.

**Temperature history is worth ~nothing because the trace is decorative.**
`shipments.rs::truth_transit_trace` draws a ramp plus jitter, then bisects a constant
offset until the trace's `φ̄` *exactly equals the `φ̄` already drawn* from the truncated
normal. The trace is a rendering of two scalars, and one of them barely moves
(`σ_T = 0.53 °C` at `q10 = 3` gives `φ̄` a ~5% spread). Measured consequence, from
`docs/findings/why-pack-date.md`: `Var(log d) = 0.205` vs `Var(log φ̄) = 0.00335`, a
98.4 / 1.6 split. A pack date is a duration measurement, so it removes 98.4% of
shipment-level exposure uncertainty and a full trace can only mop up the remaining 1.6%.

**LGTIN is worth ~nothing because lot identity is redundant with shelf age.** One lot per
delivery on a M/W/F schedule means every lot on the shelf has a distinct age, and age
already orders freshness — so pooled counts nearly pin the sales allocation anyway.
Measured ladder: books-only 0.109 → pack-date 0.034 → *lot ID +* pack-date 0.032.

Intended outcome: both channels earn their place. Three lots per delivery with different
journeys makes per-lot attribution genuinely informative (three *same-age* lots at very
different freshness cannot be told apart by age). Cold-chain break events raise `φ̄`'s
share of exposure variance from ~1.6% to ~20%, so a trace carries information a date
cannot. Hard constraints: **no meaningful increase in per-day filter runtime**, and the
equations must stay simple — in particular the truncated-normal transit temperature goes
away rather than getting more complicated.

This supersedes **ADR 0038** (MOD-16), which chose "exactly one lot per delivery" against
its own card's recommendation of option C, and says *"do not reopen without asking
Oliver."* Oliver reopened it. The design below is option C with a fixed, known `L = 3`
(the ADR's option B — inferring `L` as a latent — stays rejected as transdimensional).

## Design

### 1. Cold-chain breaks replace the truncated-normal temperature

A **break** is a discrete episode where product leaves refrigeration: a pallet on an
unrefrigerated dock during loading, a cross-dock transfer, a reefer off with doors open, a
missed connection leaving a shipment in warm staging. Thermal damage concentrates at
handoffs, not during steady-state line-haul — hence an event model rather than "the truck
ran a bit warm."

```
N  ~ Poisson(ρ · d)                 break count; hazard constant per transit-day
τ_j ~ Exp(τ̄)   at fixed T_break     break duration (the thing that physically varies)
Λ   = (d − Στ_j)·φ_set + Στ_j·φ_break
    = d·φ_set + Σ ε_j,               ε_j = τ_j·(φ_break − φ_set)
```

The trip clock runs during a break, so the second line is **exact, not an approximation**.
Since `ε_j` is a fixed multiple of `τ_j` it is still exponential, so given `N` the break
total is `Gamma(N, m)` — quantile-invertible with the `gamma_dist_quantile` already in
`arrival.rs`.

Four parameters, all in physical units: `T_set`, `T_break`, `ρ`, `τ̄`. Starting values
`T_break = 12 °C`, `τ̄ = 12 h`, `ρ = 0.08 /day` put a typical break at ~1.2 reference-days
and the duration share near 80%.

> Do **not** draw severity as a temperature excess. `ΔT ~ Exp(6 °C)` makes
> `φ = q10^(ΔT/10)` Pareto with tail index ≈ 1.5 — infinite variance and unstable
> quadrature. Drawing the duration at a fixed temperature avoids this entirely.

**The trace becomes the generative primitive.** Lay out K deterministic legs with fixed
duration shares and setpoints (pre-cool/staging 0.5 °C for 15%, line-haul 2 °C for 60%,
dock/receiving 5 °C for 25%) — deterministic, so zero inference cost; it only makes
`φ_set` the weighted average `Σ w_k φ(T_k)`. Draw `N` break start times uniformly on
`[0, d]`, punch in rectangular pulses to `T_break` of length `τ_j` (clamped to not overrun
the trip), then compute `Λ` from the trace via the **existing**
`arrival.rs::resolve_arrival_exposure`.

Deletions: the bisection loop in `truth_transit_trace`, `sample_truncated_normal`,
`truncated_normal_quantile`, `normal_cdf`, `erf`, and the `mu_T` / `sigma_T` /
`temp_floor_c` artifact fields. `normal_quantile` stays (ψ still needs it).

Filter side: the 8-node Gauss quadrature over the truncated normal is replaced by
enumeration of `N = 0..4` with Poisson weights, 8 nodes on the `Gamma(N, m)` when `N ≥ 1`
— 33 thermal nodes.

### 2. Three lots per delivery, DC model with a shared final leg

`L = 3` fixed and known (latent `L` deferred). Delivery quantity is **split** across the
three lots, not multiplied — total units per delivery is unchanged, which is what keeps
runtime flat.

```
Λ_ℓ = Λ_upstream,ℓ + Λ_shared
```

Each lot draws its own upstream journey (own duration, own breaks — different growers,
regions, pack dates); one DC→store leg is drawn per delivery and shared. Traces are
spliced: three journeys diverging early and converging onto an identical tail.

This is nearly free because **the filter never conditions on legs** — only on total
duration (pack date) or total exposure (trace). It is purely a truth-path and
trace-rendering change, made trivial by the exposure additivity above. It also fixes the
correlation structure honestly: lots on one truck become correlated but not identical.

### 3. Under UPC the delivery is one cohort; under LGTIN it is three lots

A UPC store's inventory record *is* one undifferentiated pile — it cannot track three
cohorts it can't tell apart at the register. So:

- **LGTIN:** three segments, each born from its own `ArrivalCondition` (`Duration(d_ℓ)` or
  `Exposure(Λ_ℓ)`), each scorable per-lot for sales and waste.
- **UPC:** one segment of `Q` units, born from the mixture
  `Law_UPC = (1/L) Σ_ℓ Law(record_ℓ)`.

The UPC store still *receives* all L records (the ASN lists three dates; three loggers
came back) — it just cannot attribute them, so the laws get mixed. **Mix the laws, don't
average the dates:** a mixture of three laws with different means has variance including
the between-lot spread; averaging dates first would leave only within-lot variance.

Three things LGTIN now buys, in descending order of expected effect:

1. **Sequential attribution.** Pooled totals cannot distinguish "sales came from the fresh
   lot, leaving a stale shelf" from the reverse. The multinomial allocation term can.
   Particles genuinely differ in allocation (picking is weight ∝ `f^σ`); under UPC nothing
   penalises that diversity, so the posterior spreads further every day.
2. **Composition.** Under LGTIN the bag is exactly 13/13/14 units per lot; under UPC it's
   roughly Multinomial(Q, ⅓,⅓,⅓), a spread of ~±3 units per lot.
3. **Lot count** — ADR 0038's uncounted third channel, obtained with no transdimensional
   inference because the low rung simply assumes one and the error is measured.

**No new mask fields, and the three switches stay orthogonal.** `delivery_history`
controls what journey data arrives; `code_type` controls whether you can hold it in
segments. The `waste_by_lot` → `code_type` coupling at `obs.rs:224` remains the sole
documented exception. An earlier draft of this plan proposed a coupled
`delivery_history_by_lot` field — **do not add it**; the structural fork subsumes it.

### 4. Runtime

Per-day filter cost (~5.7 ms at N=200) is unaffected by the arrival model — it only shows
up at **birth**, where sampling is a binary search over a cached CDF table. The cost is
*building* that table: `4096 grid points × product quadrature over the unpinned
nuisances`.

| Law | Unpinned | Evals/build | Built |
|---|---|---|---|
| P0 prior | duration × thermal × ψ | 8×8×8×4096 ≈ 2.1M | once per session |
| F2 pack date | thermal × ψ | 8×8×4096 ≈ 262k | once per distinct integer day (~8 ever) |
| F3 trace | ψ only | 8×4096 ≈ 33k | **every delivery** (Λ continuous, cache never hits) |

Thermal node count (8 → 33) touches only P0 and F2 — cached, startup-only. Multi-lot
touches only F3 — 3× more builds per delivery. Both are paid for by **reducing
`ARRIVAL_GRID` from 4096 to 512** (`arrival.rs:19`), an 8× cut across every row at an
inverse-sampling resolution of 0.002 in freshness, far below any noise floor here.

Secondary: shelf segment count goes from ~3–5 to ~9–15 under LGTIN. Per-lot Poisson-binomial
DP is `O(n_ℓ·w_ℓ)`, so three smaller lots cost *less* than one large one at fixed total
units — but per-lot loop overhead and the `L×K` belief-wire payload both triple. Measure,
don't assume.

## Files to change

**Rust kernel** (`crates/voi_core/src/`):

- `arrival.rs` — the bulk. Replace `mu_t`/`sigma_t`/`temp_floor_c` with break parameters;
  delete `sample_truncated_normal`, `truncated_normal_quantile`, `normal_cdf`, `erf`;
  replace the thermal branch of `marginal_cdf_at` with the Poisson×Gamma enumeration; add
  a mixture-of-conditions law for the UPC cohort; rewrite `draw_truth_delivery` to emit
  `L` sub-lots with per-lot traces plus a shared leg; drop `ARRIVAL_GRID` to 512.
- `shipments.rs` — rewrite `truth_transit_trace` as legs + break pulses (delete the
  bisection loop). `resolve_arrival_exposure` / `arrival_exposure_from_path` are reused
  unchanged.
- `session.rs::advance_one` (~line 432–489) — mint `L` lot ids instead of one; build the
  per-lot draws and traces; populate `RichDay.arrival_lot_ids` (already `Vec<i64>`) and a
  per-lot trace list.
- `unit_pf.rs` — birth block (~line 555–587): replace the `.first()` lot id and single
  `push_lot_births` call with a loop over sub-lots under LGTIN, or one merged cohort under
  UPC. `resolve_arrival_f_law` (~line 300) becomes per-lot rather than per-delivery.
- `obs.rs` — `FilterObs` carries per-lot pack dates and per-lot traces. **No new mask
  field.**
- `unit_ll.rs` — no change expected; `pb_loglik_by_lot`, `loglik_sales_by_units`,
  `lot_shares_from_freshness` already loop over `n_lots` generically.

**Artifact**: `data/abdella/arrival_model.json` — schema version bump; swap `mu_T` /
`sigma_T` / `temp_floor_c` for leg setpoints and `T_break` / `rho` / `tau_bar`; add
`lots_per_delivery`. `scripts/fit_abdella_arrival.py` and
`scripts/arrival_calibration_note.py` follow.

**Calibration guard** (`scripts/arrival_calibration_note.py`): the six Abdella shipments
are six observations of a chain that *never broke*. Re-express the guard as: **at ρ → 0
the model reproduces the six shipments' 98.4% duration share.** One model, one corridor,
guard still checked against data on exactly the regime the data covers; `ρ` and `τ̄` become
the openly-assumed parameters, assumed precisely because six clean traces cannot estimate
a break frequency.

**Wire / TS / Python mirrors**: `arrival_wire.rs`, `belief_flat.rs`,
`web/src/engine/types.ts`, `web/src/obsMask.ts`, `src/blueberries_voi/filter/types.py`.
`web/src/charts/deliveryTempChart.ts` and `EventsPane.tsx` already read
`temp_traces_by_lot`, so the studio is mostly pre-plumbed.

**ADR**: new ADR superseding 0038, recording the move to option C with fixed `L = 3`, and
a second ADR (or the same one) for the break model superseding the relevant part of 0144.

## Verification

1. `cargo test -p voi_core -p voi_wasm` — expect `t140_arrival_gamma`,
   `t141_*`, `t150_phase2_arrival_model`, `t_events_temp_trace`, `unit_pf_ac` to need
   updating.
2. **Ladder ordering must still hold**:
   `crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`
   asserts MAE strictly increases from richest to least-informed. This is the primary
   correctness gate — if the new model breaks monotonicity, something is wrong.
3. **Runtime, measured before and after**, not asserted: `cargo run -p voi_core --release
   --bin bench_day_timing` for per-day cost, and time a full 90-day `EngineSession` run to
   capture session-startup law builds. Target: per-day within noise of today's ~5.7 ms at
   N=200; total episode time not materially worse.
4. **Variance decomposition**: re-run `scripts/arrival_calibration_note.py` and confirm the
   duration share lands near the target (~80%) at default `ρ`, and recovers 98.4% at
   `ρ = 0`.
5. `uv run pytest -n auto` for the Python mirrors and wire parity
   (`test_rust_parity.py`, `test_simulator_belief_wire.py`, `test_t128_obs_channels.py`).
6. Re-run `notebooks/13_filter_accuracy_knowledge_ladder.ipynb` to get fresh ladder
   numbers. Expect F2a to separate from F2 (currently 0.034 vs 0.032) and the
   temperature step to grow beyond its current halving.
7. Studio smoke: `./scripts/build-wasm.sh && ./scripts/studio.sh`, step a few delivery
   days, confirm the Events pane renders three per-lot traces with visible break pulses.

Per your scope answer: docs prose in `docs/findings/` and `docs/store/` is **deferred** to
a follow-up pass, but the notebooks get re-run so the numbers exist. Note that
`tests/test_docs_code_refs.py` pins `file:line` references — expect it to fail on
`arrival.rs` and `shipments.rs` and to need re-pinning even in the deferred-docs scope.
