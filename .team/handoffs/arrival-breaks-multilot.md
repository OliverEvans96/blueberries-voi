# Handoff — multi-lot deliveries + cold-chain break events

**Date:** 2026-08-26 · **Owner:** Oliver (repo owner, approved the plan directly)

## Plans (read in this order)

1. **Transit thermal/duration (Stage 1) — CURRENT AUTHORITY:**
   [`.team/plans/arrival-transit-generative-v2.md`](../plans/arrival-transit-generative-v2.md)  
   Bottom-up Abdella-matched stage times, trip cool/nominal/warm mode, required hourly
   OU on charts, 0150-style breaks, closed-form filter projection, calibration recipe.
   **Do not accept Stage 1 as done against deterministic fixed legs alone.**
2. **Multi-lot + original breaks plan (Stage 2+; §1 thermal superseded):**
   [`.team/plans/arrival-breaks-multilot.md`](../plans/arrival-breaks-multilot.md)  
   Still authority for three lots / UPC mixture / shared DC leg. Header notes §1 supersession.

This handoff records branch state, corrections, and open questions.

The previous agent was acting as **manager only** at Oliver's explicit instruction:
*"delegate the actual implementation only to sonnet subagents — you are just the manager —
do not implement yourself."* Honour that unless Oliver says otherwise. Also binding:
*"work in a worktree (multiple if using concurrent subagents), and open a single PR at the
end."*

---

## Why this change exists

Two observation channels in the knowledge ladder buy almost nothing, both for modelling
reasons rather than genuine findings:

- **Temperature history**: `shipments.rs::truth_transit_trace` fabricated a trace and then
  bisected a constant offset until its `phi_bar` matched an already-drawn scalar. The trace
  carried no information beyond two numbers, one of which barely moved (`sigma_T = 0.53 C`).
- **LGTIN**: with one lot per delivery on a M/W/F schedule, every shelf lot has a distinct
  age, and age already orders freshness — so pooled counts nearly pin the sales allocation.
  Measured ladder: books-only 0.109 → pack-date 0.034 → *lot ID +* pack-date 0.032.

---

## Branch / worktree state

PR **#65** is open on `team/arrival-breaks/integrate` (this checkout).

| Worktree / branch | Stage | Status |
|---|---|---|
| `team/arrival-breaks/integrate` (PR tip) | merge of adr + core | Open WIP |
| `.worktrees/arrival-breaks-core` | Stage 1 thermal (old brief) | Partial deterministic-legs+breaks — **must be revised to v2 plan before accepting** |
| `.worktrees/arrival-breaks-adr` | ADRs 0149/0150 | Done; **0150 baseline wording needs amend when implementing v2** |
| Stage 2 wiring / Stage 3 mirrors | multi-lot + version bump | Not started |

### Stage 1 — REVISE TO TRANSIT GENERATIVE v2 (do not ship deterministic-legs-only)

Partial implementation exists for ADR 0150 deterministic legs + breaks (`arrival.rs`,
`shipments.rs`, `arrival_model.json`, `t151_cold_chain_breaks.rs`). That is a useful
scaffold but **not** the accepted generative story anymore.

**Next agent (implementation):** follow
[`.team/plans/arrival-transit-generative-v2.md`](../plans/arrival-transit-generative-v2.md)
end-to-end (§6 sequence). Reuse break math and tests where they still apply; replace
fixed leg shares with bottom-up Abdella-matched stage gammas; add trip modes + hourly OU;
extend filter `thermal_nodes`; update fit script / guards; demote haul chips.

Verify with `cargo test -p voi_core -p voi_wasm` (and focused arrival tests listed in v2)
before starting Stage 2.

### ADR stage — done and verified

ADRs **0149** (three fixed lots per delivery, supersedes 0038) and **0150** (cold-chain
break events, supersedes the transit-temperature clause of 0144). `test_docs_adr_status.py`
passes in that worktree (verified, 2 passed).

Two findings from that stage worth carrying forward:

1. **ADR 0148 is also affected** and the plan missed it — it fits the truncated-normal
   moments in `scripts/fit_abdella_arrival.py`. Now partially superseded by 0150.
2. **A prior architect report disagrees with fixed `L = 3`.**
   `.team/reports/mod-16-filter-options.md` (T-129, "Draft for human review") recommended
   random `L ∈ {1,2,3}`, as does the MOD-16 entry in `.team/backlog.md`. Oliver's own
   framing was *"perhaps the number of lots per delivery should actually be a latent
   variable at lower observation rungs. But for now, we could just assume it's always 3."*
   Fixed-3 is therefore deliberate, with latent-`L` as the deferred follow-up. ADR 0149
   records the divergence rather than burying it.

---

## OPEN ISSUE — calibration guard (RESOLVED by transit generative v2)

The original plan’s *“at ρ→0 reproduce 98.4% duration share”* guard is unachievable under a
**fully deterministic** legged baseline (share → 100%). That was the defect.

**Resolution (Oliver, 2026-08-26 design pass → `arrival-transit-generative-v2.md`):**

- Keep `Var(log d) ≈ 0.205` as a hard duration check (Abdella match via bottom-up stage gammas).
- Restore **mild clean-chain φ̄ scatter** with trip thermal modes + hourly OU, tuned so that
  at `ρ=0` mean/SD of `φ̄` match the six shipments (simple moment metrics — not MLE).
- Default-`ρ` duration-vs-break variance share remains a **design/scenario** number (~80%),
  not something estimated from six clean traces.
- Breaks stay inside total calendar `d` (see undecided note below — still locked as inside).

### Related, un-decided: do breaks extend the trip or sit inside it?

The plan takes `d` as **total** calendar duration with breaks as periods *within* it, which
is what makes `Lambda = d*phi_set + sum eps_j` exact. Consequence: a pack date carries **no
direct signal** about whether a break occurred — duration and break damage couple only
weakly, through the `Poisson(rho*d)` rate.

The alternative (`d` = moving/cold time, breaks add on top, total = `d + sum tau_j`) would
make a longer-than-expected trip *itself* evidence of a break. That is arguably more
realistic and would make the pack date **more** valuable — partly offsetting the temperature
gain this whole change is trying to create. Worth putting to Oliver, since it cuts against
the project's goal. At default parameters breaks consume only ~4% of transit time, so the
numerical difference is small; the *inferential* difference is not.

---

## Remaining work

### Stage 2 — multi-lot deliveries
Branch **off Stage 1's tip, not `main`** (it builds on the new arrival API).
`git worktree add .worktrees/arrival-breaks-wiring -b team/arrival-breaks/wiring team/arrival-breaks/core`

- `session.rs::advance_one` (~432–489): mint `L = 3` lot ids instead of one; per-lot
  upstream journeys plus one shared DC→store leg; populate `RichDay.arrival_lot_ids`
  (already `Vec<i64>`) and a per-lot trace list.
- `unit_pf.rs` birth block (~555–587): replace the `.first()` lot id and single
  `push_lot_births` call. **Under LGTIN** push three segments, each from its own
  `ArrivalCondition`. **Under UPC** push one merged cohort of `Q` units from the mixture law
  Stage 1 added (`Law_UPC = (1/L) sum_l Law_l` — the pointwise average of the component
  cached CDFs; mixture variance is *not* the average of component variances).
  `resolve_arrival_f_law` (~300) becomes per-lot rather than per-delivery.
- `obs.rs`: `FilterObs` carries per-lot pack dates and traces. **No new mask field** — an
  earlier draft proposed `delivery_history_by_lot`; it is rejected, the structural fork
  subsumes it. The three switches stay orthogonal.
- `unit_ll.rs`: no change expected, it already loops over `n_lots` generically.
- Delivery quantity is **split** across lots, not multiplied — this is what keeps runtime flat.

### Stage 3 — mirrors and guards
Python (`src/blueberries_voi/filter/types.py`), TS (`web/src/engine/types.ts`,
`web/src/obsMask.ts`), wire (`arrival_wire.rs`, `belief_flat.rs`),
`scripts/fit_abdella_arrival.py`, and **bump `web/package.json` version** —
`crates/voi_core/` is a publishable path and `test_studio_release_version.py` enforces it.
The studio is mostly pre-plumbed: `deliveryTempChart.ts` and `EventsPane.tsx` already read
`temp_traces_by_lot`.

### Integration
Merge all branches into `team/arrival-breaks/integrate`, run the CI-parity gate on Python
3.11 (`ruff check` · `ruff format --check` · `mypy src tests` · `pytest -n auto --cov`),
then open **one** PR.

---

## Known-red at PR time (both from decisions already made)

- **The `docs` CI job.** Oliver chose "model + guards, docs deferred". AGENTS.md treats docs
  as part of the change and the `docs` job is a hard gate, so it will fail until the
  follow-up pass. Pages needing rewrite: `docs/store/cold-chain-arrival.md`,
  `docs/findings/why-pack-date.md`, `docs/findings/does-belief-sharpen.md`,
  `docs/inference/upc-vs-lgtin.md`, `docs/ladder/channels.md`,
  `docs/ladder/observation-scenarios.md`, `docs/inference/birth-freshness.md`.
  `test_docs_code_refs.py` pins `file:line` citations and will fail on `arrival.rs` /
  `shipments.rs` regardless.
- Notebooks get re-run so fresh numbers exist (`notebooks/13_filter_accuracy_knowledge_ladder.ipynb`),
  but prose is deferred.

## Verification targets

- **Primary correctness gate:** `t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`
  — belief MAE must strictly increase from richest scenario to least-informed. Never relax it;
  a failure means the model is wrong.
- **Runtime, measured not asserted:** `cargo run -p voi_core --release --bin bench_day_timing`.
  Baseline is ~5.7 ms/day at N=200. Per-day cost should be within noise; the arrival model
  only touches *birth*. `ARRIVAL_GRID` 4096→512 is what pays for both the extra thermal
  nodes (8→33, cached/startup-only) and the 3× F3 law builds from multi-lot.
- Expect F2a to separate from F2 (currently 0.034 vs 0.032) and the temperature step to grow.
