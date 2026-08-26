# Handoff — multi-lot deliveries + cold-chain break events

**Date:** 2026-08-26 · **Owner:** Oliver (repo owner, approved the plan directly)
**Approved plan:** `/home/oliver/.claude/plans/i-d-like-to-make-humming-reddy.md` — read this
first, it is the authority. This document only records state and open questions.

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
- **GSIN**: with one lot per delivery on a M/W/F schedule, every shelf lot has a distinct
  age, and age already orders freshness — so pooled counts nearly pin the sales allocation.
  Measured ladder: books-only 0.109 → pack-date 0.034 → *lot ID +* pack-date 0.032.

---

## Branch / worktree state

Nothing is committed anywhere. Nothing is pushed. No PR exists yet.

| Worktree | Branch | Stage | Status |
|---|---|---|---|
| `.worktrees/arrival-breaks-core` | `team/arrival-breaks/core` | 1 — thermal model | **In flight**, agent may have been cut off mid-run |
| `.worktrees/arrival-breaks-adr` | `team/arrival-breaks/adr` | ADRs | **Done, reviewed** |
| *(not yet created)* | `team/arrival-breaks/wiring` | 2 — multi-lot | Not started |
| *(not yet created)* | `team/arrival-breaks/mirrors` | 3 — mirrors/guards | Not started |

Main tree is on `main`, clean.

### Stage 1 — IN FLIGHT, verify before continuing

Its agent was still running when the session ended. Last observed state:

```
 M crates/voi_core/src/arrival.rs      (+595 / heavily reworked)
 M crates/voi_core/src/session.rs      (+30, mechanical compile fixes only)
 M crates/voi_core/src/shipments.rs    (+151)
 M data/abdella/arrival_model.json     (+44)
 ?? crates/voi_core/tests/t151_cold_chain_breaks.rs   (new)
```

**First action for the next agent:** run `cargo test -p voi_core -p voi_wasm` in that
worktree. If it is green and the work is coherent, keep it and move to Stage 2. If it is
half-finished, either re-task a Sonnet subagent to finish it against the same brief, or
`git checkout -- .` and restart Stage 1. Do not assume it is complete — no completion
report was ever received.

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

## OPEN ISSUE — the calibration guard as written is unachievable

Oliver asked about transit-duration variance, and working through it exposed a real defect
in the approved plan. **Resolve this before Stage 1 is accepted.**

The duration law itself is **unchanged**: `d = d_min + Gamma(delay_shape, delay_scale)`,
`abdella_all` = (1.853, 3.009, 0.974), giving `d ≈ 4.78 ± 1.69` days and
`Var(log d) ≈ 0.205` — matching the six shipments. Breaks do not touch it.

The plan says to re-express the calibration guard as *"at `rho -> 0` the model reproduces
the six shipments' 98.4% duration share."* **It cannot.** With a fully deterministic legged
baseline, `rho -> 0` gives `Lambda = d * phi_set` with `phi_set` constant, so
`Var(log Lambda) = Var(log d)` exactly and the duration share is **100%, not 98.4%**. The
missing 1.6% in the real data comes from genuine trip-to-trip variation in `phi_bar`, which
the new model deliberately removed.

Three ways out, in preference order:

1. **Re-express the guard as a direct duration check** — at `rho -> 0`, the model's
   `Var(log d)` matches the observed `0.205`. Still data-anchored, no share arithmetic,
   no new parameters. *Recommended.*
2. Restore a small per-leg setpoint jitter sized to reproduce the observed 1.6%. Exactly
   reinstates the guard and is arguably more honest about real reefers — but Oliver was
   offered this ("keep legs stochastic too") and did **not** pick it, and it reintroduces a
   continuous thermal nuisance to quadrature over. Do not adopt without asking.
3. State the guard as a bracket: observed 98.4% sits between the `rho = 0` limit (100%) and
   the default-`rho` value (~80%). Weakest; asserts little.

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
  `push_lot_births` call. **Under GSIN** push three segments, each from its own
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
  `docs/inference/upc-vs-gsin.md`, `docs/ladder/channels.md`,
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
