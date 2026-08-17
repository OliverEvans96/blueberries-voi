# MOD-16 revisit — filter stance options for multi-lot deliveries (1–3 lots)

**Date:** 2026-08-16  
**Ticket:** T-129 (report-only; no implementation)  
**Team role:** architect  
**Status:** Draft for human review before superseding ADR [0038](../adr/0038-mod-16-lots-per-delivery-below-the-scanning-rung.md)

**Related ADRs:** [0038](../adr/0038-mod-16-lots-per-delivery-below-the-scanning-rung.md) (current settle),
[0015](../adr/0015-scn-f1-sunrise-partial-lot-id-at-pos.md) (SCN-F1 / lot ID at POS),
[0048](../adr/0048-fil-03-arrival-age-discretisation.md) (FIL-03 arrival-age grid),
[0049](../adr/0049-fil-04-factorisation-of-age-across-cohorts.md) (FIL-04 age factorisation; superseded in production by 0091 mean-field),
[0130](../adr/0130-f-native-c2-a-unit-pf.md) (f-native C2-A unit PF production path)

**Code / docs reviewed:** `crates/voi_core/src/day_step.rs`, `unit_pf.rs`, `obs.rs`, `session.rs`;
[`.team/docs/f-native-unit-pf-explainer.md`](../docs/f-native-unit-pf-explainer.md);
[`.team/backlog.md`](../backlog.md) (planned modeling item);
`experiments/c2_a_totals_study.md` (T-C2-A timing);
`web/src/react/EventsPane.tsx` (events wire consumption).

---

## Executive summary

Oliver reopened **MOD-16** in the backlog: move from **one arrival cohort per delivery** (ADR 0038 option A) to **honest multi-lot deliveries** where the number of physical GS1 lots per delivery is a random variable, typically **1–3**, driven by order quantity and DC-picking behaviour ([MOD-01](../adr/0023-mod-01-unit-of-inventory-state.md)).

This report compares three filter stances for that revisit on the **f-native C2-A unit PF** stack (ADR 0130).

| Option | One-line | Recommendation |
|--------|----------|----------------|
| **A — Honest multi-lot** | Sim mixes; filter injects **one birth cohort per physical lot** (k FIFO shifts per delivery day) | **Recommended** |
| **B — Transdimensional** | Filter infers **how many** lots arrived (ADR 0038 option B) | Defer |
| **C — Structured bias** | Sim mixes; filter assumes **one lot per delivery** (ADR 0038 option C) | Reject for production |

**Recommendation: Option A.** It aligns simulator truth with filter state (no silent structural mismatch), keeps the existing particle-bank shape (fixed `L×U` grid, no transdimensional birth–death), and stays inside the measured T-C2-A compute envelope with modest `L_DIM` headroom. Option B is scientifically complete for the SCN-F1 “lot count is information” channel but is disproportionate engineering for effect size. Option C preserves tractability at the cost of **measured, scenario-dependent bias** on every VOI difference — unacceptable for a project whose headline numbers are small profit deltas.

---

## Current state — ADR 0038 option A (1:1 delivery–cohort)

### What is settled today

ADR [0038](../adr/0038-mod-16-lots-per-delivery-below-the-scanning-rung.md) adopted **option A — exactly one lot per delivery, always**. The simulator never mixes receipts within a delivery; “lot” and “delivery cohort” are equivalent in all but name.

### How the f-native stack implements A

| Layer | Behaviour on delivery |
|-------|-------------------------|
| **Ground truth** (`unit_day_step`) | Appends **one** `lot_offsets` segment; all `deliver_units` share one `birth_f` from `delivery_birth_f` |
| **Filter** (`filter_step_unit`) | **One** FIFO eviction (`drain(0..U)`) + append `U` units with a single `birth_f` draw |
| **Session** (`EngineSession::step`) | Pushes **one** `lot_id` per arrival day |
| **RichDay / wire** | `sales_by` / `waste_by` indexed by **ground-truth lot count**; `lot_ids` is the live-lot id vector **before** the day’s pick/spoil (one new id appended on delivery) |

Virtual filter slots (`L` = `DEFAULT_L_DIM` = **10**, `U` = **15**) are a sliding FIFO window over delivery cohorts, not GS1 lot IDs. Truth uses variable-length `lot_offsets`; the filter uses fixed `L×U` ([f-native explainer](../docs/f-native-unit-pf-explainer.md) §4).

### Why reopen

MOD-01 and the MOD-16 card both state the honest logistics position: **one to three lots per delivery, usually dominated by one**. ADR 0038 explicitly noted a **VOI channel** — below the lot-scanning rung you cannot observe how many lots a delivery contained; at SCN-F1 you can ([0015](../adr/0015-scn-f1-sunrise-partial-lot-id-at-pos.md)). Staying on option A **understates** that channel and forces bimodal physical mixtures into a single within-lot spread (MOD-05), which breaks when Chile/Mexico receipts land in one DC pick.

---

## Lot-count PMF sketch (1–3 lots, order-qty driven)

A pragmatic generative model for exploration and tests (not yet coded):

### Inputs

- `order_qty` — case-rounded delivery size (default `case_size = 8`; typical orders 8–48+ units).
- `case_size` — GS1 case / clamshell pack size (one lot per case at packhouse).
- Latent **mixing propensity** `π_mix` — store/season knob; default low (0.05–0.15) for fast-turning berries.

### Proposed PMF

Let `n_cases = ⌈order_qty / case_size⌉` (at least 1 when `order_qty > 0`).

| Regime | P(k lots) | Notes |
|--------|-----------|-------|
| `n_cases = 1` | P(1) = 1 | Single-case delivery → one lot by construction |
| `n_cases = 2` | P(1) = 1 − π_mix, P(2) = π_mix | DC may combine two receipts or ship as two cases |
| `n_cases ≥ 3` | P(1) = (1 − π_mix)², P(2) = 2π_mix(1 − π_mix), P(3) = π_mix² (renormalize tail) | Cap k at 3; redistribute mass from k > 3 |

**Unit split:** Given k lots and total `order_qty`, allocate units multinomially with Dirichlet(α,…,α) weights (α ≈ 2 favours uneven splits without extreme 1-unit lots). Each lot draws **independent** `birth_f` from the knowledge scenario (F2 Dirac, F2a Gaussian, or mixed prior) — mirroring distinct receipts.

**Exploration default:** `π_mix = 0.10`, `case_size = 8`, MWF delivery cadence → E[k] ≈ 1.1–1.3 on delivery days for typical order sizes 16–32.

---

## Option A — Honest multi-lot

> Simulator mixes receipts within a delivery; filter injects **one virtual cohort birth per physical lot** (k FIFO shifts on delivery days).

### Interpretability

| Audience | Story |
|----------|-------|
| **Produce managers** | “Your delivery might be 2–3 traceable lots; the model tracks each separately.” Matches GS1 mental model. |
| **VOI readers** | Below F1, lot **count** is latent but **assumed from the generative delivery model** (same as truth). At F1+, `sales_by` + `lot_ids` align with multiple live lots — the ladder’s “how many lots do I have?” channel is **honest below F1** (known support) and **observable at F1**. |
| **Studio users** | Events pane can show **multiple delivery lot cards** per day; belief heatmap gains rows when k > 1. Slightly busier UI, but truthful. |

### Compute time impact

**Baseline (T-C2-A):** production `filter_step_unit` @ `N=200`, `U=15`, P1 totals — **5.7 ms/day mean** @ `L=20` (p95 6.1 ms); scales ~linearly in `L×U` ([`experiments/c2_a_totals_study.md`](../../experiments/c2_a_totals_study.md)).

**Arrival incremental cost:** Today one delivery performs **one** `drain(0..U)` + `extend(U × birth_f)` per particle. Option A performs **k** such shifts per delivery day.

| k on delivery day | Arrival work vs today | Notes |
|-----------------|----------------------|-------|
| 1 (majority) | 1× | Unchanged |
| 2 | 2× arrival slice | ~10–20% of delivery days under PMF sketch |
| 3 | 3× arrival slice | Rare; promotional / region-mix scenarios |

**Episode-level estimate:** With E[k] ≈ 1.15 and deliveries on ~3/7 days, **mean filter-day cost rises ~5–8%** — still **≪ 500 ms/day** studio budget (87× headroom @ L=20). Worst-case single day (k=3 on delivery + full P1 likelihood over more live slots) remains **< 20 ms** extrapolated.

**VOI grid:** `run_voi_crn_cell` replays the same path; cardinality multiplies by scenario count, not by k. Per-cell cost grows with the modest arrival factor above.

### Memory impact

| Resource | Today (A) | Option A |
|----------|-----------|----------|
| **Particle state** | `N × L × U` floats | Same shape; **more slots hold live mass** concurrently |
| **`L_DIM`** | 10 default | May need **12–15** if peak concurrent **delivery cohorts** (not lots) × k exceeds window — remeasure under CAL-01 MWF cadence ([CAL-01-fil13-remeasure-L.md](./CAL-01-fil13-remeasure-L.md)) |
| **Peak concurrent lots** | ≈ concurrent deliveries | ≈ **k_max × concurrent deliveries** in worst case (k_max = 3) |
| **RichDay vectors** | `sales_by.len()` = live lot count | Grows with truth lot count; already variable-length in ground truth |

FIL-03 ([0048](../adr/0048-fil-03-arrival-age-discretisation.md)): `f_grid` / `K` unchanged. Cost is in **number of live lot slots with mass**, not arrival-age grid points.

### VOI / SCN-F1 cardinality story

- **Below F1 (P0/P1):** Lot count is **not observed** but is **shared identically** in sim and filter (known support). VOI compares observation schemes holding the generative delivery model fixed — valid.
- **F1 / F2:** `sales_by` length = live lot count; `lot_ids_live` enumerates GS1 ids. Multi-lot deliveries **increase the length** of these vectors on observation days — already supported by `RichDay` shape; F1 likelihood in `unit_ll` scores **per virtual slot**, not per delivery.
- **New VOI channel (card note):** Jump from P1 → F1 can include **resolving lot count**, not only per-lot sales. Option A makes that jump **real in sim**; VOI attribution should separate “per-lot sales shape” from “how many lots exist.”

### Implementation complexity and risk

| Area | Work | Risk |
|------|------|------|
| `day_step` | Split `deliver_units` into k segments with independent `birth_f` | Low — extends existing delivery path |
| `unit_pf` | Loop k FIFO shifts; k distinct `birth_f` draws per particle | Low — localized to arrival block |
| `session.rs` | k `lot_id` pushes; build `RichDay` from variable `lot_offsets` | Medium — id ordering for events UI |
| Policy / belief wire | Unchanged flattening (`belief_flat_from_unit_bank`) | Low if `L_DIM` sized correctly |
| **Risk:** `L` too small | Silent eviction of live units | Mitigate by remeasure + default bump |

### Test / benchmark implications

- **Unit:** Scripted k=2,3 delivery days; assert k segments in `lot_offsets` and k FIFO shifts in filter state.
- **Regression:** T-C2-A timing gate @ L=20 with k-mixed delivery script — expect **< 10 ms/day** mean.
- **VOI:** Golden cell with π_mix > 0; F1 vector lengths match truth lot count.
- **FIL-04 / mean-field:** More live lots → slightly stronger allocation coupling below F1; rerun Stage-C-style spot check at 3 concurrent lots ([0049](../adr/0049-fil-04-factorisation-of-age-across-cohorts.md) motivation).

---

## Option B — Transdimensional (infer lot count)

> Simulator mixes; filter maintains a **posterior over k** (number of birth cohorts to inject per delivery). ADR 0038 option B.

### Interpretability

| Audience | Story |
|----------|-------|
| **Produce managers** | “We’re not sure if that delivery was one or two lots.” Honest about warehouse ambiguity. |
| **VOI readers** | **Best** articulation of the SCN-F1 value proposition: lot scanning **measures cardinality**. Pre-F1, k is integrated out. |
| **Studio users** | Hard — must show **mixture over k** or collapse for display; easy to misread as spurious precision. |

### Compute time impact

- **Birth model:** Reversible-jump or discrete **k ∈ {1,2,3}** augmentation per particle per delivery — effectively **multiply particles across k hypotheses** or nested SMC.
- **Lower bound:** Option A cost × **E[k]** in the naive “run k separate banks” formulation; principled RJMCMC adds acceptance/reject overhead.
- **VOI:** Each CRN cell may need **outer sum over k** at low rungs → **multiplicative** scenario cost unless k is marginalized analytically (not available with sequential WOR likelihood).

At `N=200`, even 3× branching threatens **15–20 ms/day** on delivery days and complicates ESS / resample — still under 500 ms, but **engineering cost dominates**.

### Memory impact

- Particle state may become **(k, freshness map)** or a union over differing unit counts — breaks fixed `L×U` alignment across particles unless padded.
- ADR 0130 explicitly chose fixed virtual grid for **particle alignment** and catch-up replay; transdimensional state fights that design.

### VOI / SCN-F1 cardinality story

- **Theoretically correct** for the hidden cardinality channel.
- **Practically:** VOI differences pre-F1 conflate **k uncertainty** with **age uncertainty** unless carefully factorized in the experimental design — easy to double-count value already captured by arrival priors (F2/F2a).

### Implementation complexity and risk

| Risk | Severity |
|------|----------|
| Breaks fixed-shape `UnitParticleBank` | **High** |
| Catch-up replay (`set_obs_scenario`, ADR 0123) with differing k histories | **High** |
| WASM / PyO3 wire for k-marginals | **Medium** |
| No production precedent in repo | **High** |

**Verdict:** Reserve for a **research milestone** with bakeoff evidence; not the MOD-16 revisit MVP.

### Test / benchmark implications

- New test harness for k-identifiability from P1 totals (likely **weak** — motivates why B is hard).
- Cannot reuse T-C2-A gates without redefining particle bank contract.

---

## Option C — Structured bias (sim mixes, filter assumes one)

> Simulator delivers k physical lots; filter still performs **one FIFO shift** and one `birth_f` per delivery day. ADR 0038 option C (card recommendation, not chosen in 0038).

### Interpretability

| Audience | Story |
|----------|-------|
| **Produce managers** | Misleading — truth shows multiple lots, belief shows one blended cohort. |
| **VOI readers** | **Worst** — bias varies by rung and π_mix; VOI deltas absorb **filter misspecification**, not observation value. |
| **Studio users** | Simple UI (unchanged), but truth overlay vs belief diverges on delivery days when k > 1. |

### Compute time impact

- **Identical to today** on the filter path (one birth per delivery).
- Simulator cost rises slightly (k birth draws in `day_step`) — negligible.

### Memory impact

- Filter unchanged; truth uses more `lot_offsets` → **truth/belief lot count mismatch** in `live_lots` vs `lot_counts` wire.

### VOI / SCN-F1 cardinality story

- **Invalid for cardinality VOI:** Sim truth has k lots; filter state has one cohort — F1 `sales_by` vectors cannot align with filter slots without ad hoc merging.
- **SCN-F1 “lots become conditionally independent”** ([0015](../adr/0015-scn-f1-sunrise-partial-lot-id-at-pos.md)) assumes the filter **represents** the same atoms the observations index.

### Implementation complexity and risk

| Aspect | Assessment |
|--------|------------|
| Filter code | **Minimal** (sim-only change) |
| Scientific integrity | **Unacceptable** for citeable VOI |
| Truth/belief audits | **Fail** ([truth-vs-belief-audit.md](./truth-vs-belief-audit.md) contract) |

ADR 0038 rejected C explicitly: “the resulting error is measured, not hidden” — but in VOI work **measured bias in the posterior is hidden** in profit deltas.

### Test / benchmark implications

- Must add **bias monitors**: e.g. mean_f MAE on multi-lot delivery days, F1 slot alignment tests (expected fail).
- T-C2-A passes timing but **fails accuracy** on k > 1 scripts.

---

## Comparative summary

| Criterion | A — Honest multi-lot | B — Transdimensional | C — Structured bias |
|-----------|---------------------|----------------------|---------------------|
| Sim/filter alignment | Yes | Partial (k posterior) | **No** |
| Interpretability | High | Medium (expert) | Low |
| ms/day @ L=20 (est.) | **6–7** | 15–30+ | **5.7** |
| `L_DIM` pressure | Moderate ↑ | High | None |
| SCN-F1 cardinality VOI | Honest support | Full | Broken |
| ADR 0130 compatibility | **Native** | Poor | Sim-only |
| Implementation risk | Low–medium | **High** | Low / high science risk |

---

## Wire and UI changes (exploration findings)

Implementation ticket(s) after ADR supersession should touch:

### Rust / Python wire

| Component | Change for Option A |
|-----------|---------------------|
| **`RichDay`** (`obs.rs`) | Optional `delivery_lot_count: u8` or infer from `lot_ids` delta on delivery days; ensure `sales_by` / `waste_by` lengths track **ground-truth lot count** (already variable) |
| **`FilterObs`** | Pass **k** into arrival path (from truth on sim replay; from generative model in filter-only mode) |
| **`session.rs` richest_log** | Append **k** lot ids per delivery; `pre_lot_ids` snapshot must include all k new ids for F1 maps |
| **`DayDelta` / events RPC** | Expose per-delivery lot list, not only `lot_ids[0]` |
| **`live_lots` overlay** | One entry per physical lot (already per offset) |
| **Belief flat** (`belief_flat.rs`) | No schema change; verify `L` covers peak concurrent **cohorts** |

### Frontend

| Component | Change |
|-----------|--------|
| **`EventsPane.tsx`** | Today uses `deliveryLotId = ev.lot_ids?.[0]` — **must list all k delivery lots** on arrival days; extend `formatLotBreakdown` pairing |
| **`obsMask.ts` / projector** | F1 maps already keyed by `lot_ids` length — test multi-lot delivery day cards |
| **Belief heatmap** | More rows with mass when k > 1; caption “virtual slot ≠ GS1 lot” remains |
| **Truth vs belief audit** | Re-run after land; delivery-day cards are primary regression surface |

### Out of scope for this report (no implementation landed)

- ADR 0038 supersession text and board ⚑ removal
- `π_mix` / lot-count PMF parameters in `ModelParams` or UI sliders
- `day_step` / `unit_pf` / `session` code changes
- VOI grid regeneration with π_mix > 0
- FIL-13 mean-field revalidation at higher concurrent lot counts
- T-128 Events pane redesign (can absorb multi-lot cards when scheduled)
- Transdimensional (option B) prototype
- Option C bias characterization experiments

---

## Recommended path — Option A

1. **Architect:** Supersede ADR 0038 option A with option A-multi (honest k-lot births); cross-ref MOD-01 B.
2. **Spec:** Acceptance criteria for k ∈ {1,2,3}, PMF sketch above, remeasured `L_DIM` under MWF.
3. **QA:** Failing tests for k=2 delivery (sim offsets, filter FIFO count, Events pane ids).
4. **Implement:** `day_step` split → `unit_pf` k-shift loop → session id push → EventsPane.
5. **Verify:** T-C2-A timing @ L=20 with mixed deliveries; spot-check FIL-04 coupling at 3 lots.
6. **VOI:** Re-attribute F1 channel to include cardinality where π_mix > 0.

**Rationale in one sentence:** Option A is the smallest change that makes the simulator, filter, and SCN-F1 observations speak the same GS1 lot language, without reopening transdimensional inference or accepting structured filter bias.

---

## References

- [`.team/backlog.md`](../backlog.md) — “Migrate arrival cohorts → proper lots (MOD-16 revisit)”
- [`.team/docs/f-native-unit-pf-explainer.md`](../docs/f-native-unit-pf-explainer.md) — virtual slots, FIFO eviction, obs routing
- [`experiments/c2_a_totals_study.md`](../../experiments/c2_a_totals_study.md) — 5.7 ms/day @ L=20
- [`crates/voi_core/src/day_step.rs`](../../crates/voi_core/src/day_step.rs) — `unit_day_step` delivery append
- [`crates/voi_core/src/unit_pf.rs`](../../crates/voi_core/src/unit_pf.rs) — `filter_step_unit` arrival FIFO
- [`web/src/react/EventsPane.tsx`](../../web/src/react/EventsPane.tsx) — `lot_ids[0]` delivery assumption
