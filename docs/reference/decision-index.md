---
title: Decision index
sources:
  adr: [0144, 0143, 0026, 0025, 0041, 0040, 0043, 0113, 0115, 0080, 0110, 0133, 0105, 0106, 0130, 0058, 0060, 0061, 0112, 0114, 0117, 0064, 0069, 0070, 0071, 0104, 0119, 0120, 0122, 0126]
  code: []
---

# Decision index

The model behind this site is the product of dozens of individually-argued design choices —
each one recorded as an Architecture Decision Record (ADR) with its context, the alternatives
considered, and why they were rejected. This page is a curated map from the topics this site
covers to the ADRs that back them, so a claim made elsewhere on the site can be traced back to
its reasoning. It is not exhaustive — the full record (150+ ADRs) lives in `.team/adr/`.

> **Figure (coming soon):** a dependency diagram of the ADRs below, grouped by topic, with
> arrows for "supersedes" relationships — in particular the T-150 remodel (ADR 0144)
> superseding ADR 0138 and ADR 0141.

Every status below was read directly from `.team/adr/INDEX.md` at the time this page was
written (2026-08-23) — not assumed. A status of **SUPERSEDED** means don't cite that ADR as
the current design; where a listed ADR superseded an older one, the older one is named so you
can see what changed.

## The idea

Two things to know before using this index. First, status matters: an ADR can be
**ACCEPTED** (settled, in production), **PROPOSED** (drafted, under review, but the described
behavior is already what's in the code — this repo's convention is to land the change and the
ADR together), or **SUPERSEDED** (no longer the current design — kept for history only).
Second, several ADRs below use vocabulary this site's prose deliberately avoids — e.g. ADR
0033's "arrival age distribution" or ADR 0017's now-dead "age at receipt" rung. Where an ADR's
own title carries retired terminology, the gloss below translates it into current vocabulary
(freshness `f`, cumulative thermal exposure `Λ`) rather than repeating the old term.

## Why it's modeled this way

Recording decisions as ADRs — rather than only as comments or commit messages — is itself a
choice: it forces a reason and at least one rejected alternative onto the record for anything
non-obvious, which is what makes a page like this possible at all. The corresponding caveat is
that an ADR records a decision *as reasoned at the time*; several ADRs referenced elsewhere in
this repo's own history (e.g. 0009, 0031, 0073, 0138, 0141) were later superseded as the model
evolved — the ADR log is a paper trail, not a live source of truth on its own. Cross-check the
status column, not just the existence of an ADR, before citing one.

## In the code

Not applicable in the usual sense — the "code" this page indexes into is the ADR log itself
(`.team/adr/`), not `crates/` or `web/src/`. Each ADR's own file cites the specific
lines of implementation it governs.

### Physics & aging

| ADR | Gloss | Status |
| --- | --- | --- |
| `0144` (`.team/adr/0144-f-native-hierarchical-arrival-model.md`) | Freshness `f` decays via a shape-scaled gamma process (`Gamma(k·φ, θ)`); single reference life `k·θ·η_ref = 1` | PROPOSED |
| `0143` (`.team/adr/0143-independent-per-unit-gamma-aging.md`) | Each unit ages via its own independent per-unit gamma draw, not a shared cohort clock | ACCEPTED |
| `0026` (`.team/adr/0026-mod-04-spoilage-law.md`) | Spoilage law: a unit exits when its freshness hits the floor | ACCEPTED |
| `0025` (`.team/adr/0025-mod-03-in-store-temperature-treatment.md`) | In-store temperature is treated as a constant driving the Q10 aging-rate factor | ACCEPTED |
| `0041` (`.team/adr/0041-mod-19-t-ref-convention.md`) | Reference temperature `T_ref = 0°C`, one absolute scale shared by transit and in-store aging | ACCEPTED |

### Arrival / cold-chain

| ADR | Gloss | Status |
| --- | --- | --- |
| `0144` (`.team/adr/0144-f-native-hierarchical-arrival-model.md`) | Arrival freshness is a hierarchical draw over duration `d`, mean transit temperature, and within-pallet position `ψ` — supersedes 0138 and 0141 | PROPOSED |
| `0040` (`.team/adr/0040-mod-18-transit-model-parameterisation.md`) | How the transit leg itself is parameterised (duration + temperature path) | ACCEPTED |
| `0043` (`.team/adr/0043-mod-21-abdella-transit-sampling-frame.md`) | Abdella cold-chain dataset is the sampling frame for transit calibration | ACCEPTED |

### Demand

| ADR | Gloss | Status |
| --- | --- | --- |
| `0113` (`.team/adr/0113-mod-09-calendar-demand.md`) | Demand is a known negative binomial with day-of-week × week calendar structure — supersedes 0031 | ACCEPTED |
| `0115` (`.team/adr/0115-freshnet-derived-demand-product.md`) | The calendar demand profile is derived from the FreshNet retail dataset | ACCEPTED |
| `0080` (`.team/adr/0080-mod-26-demand-case-shelf.md`) | Base demand numbers: mean 30/day, variance-to-mean 2, case size 8 | ACCEPTED |

### Observation ladder

| ADR | Gloss | Status |
| --- | --- | --- |
| `0110` (`.team/adr/0110-studio-obs-scenario-ladder.md`) | The studio's `obs_scenario` knob is the same P0…F3 rung ladder used by the filter | ACCEPTED |
| `0133` (`.team/adr/0133-observation-channel-toggles.md`) | POS / waste / delivery observation channels toggle independently rather than only in fixed rung bundles | ACCEPTED |
| `0105` (`.team/adr/0105-arrival-only-age-counts-only-exact-wor.md`) | The production filter is a counts-only particle filter with exact sequential-without-replacement weights, observing only arrival-time information | ACCEPTED |
| `0106` (`.team/adr/0106-shelfbelief-arrival-prior-age-exports.md`) | The belief the controller sees is exported directly from the filter's arrival-prior particles | ACCEPTED |
| `0130` (`.team/adr/0130-f-native-c2-a-unit-pf.md`) | Both truth and filter run on the same freshness-native, per-unit particle representation (the `L×U` grid) | ACCEPTED |

### Control / ordering

| ADR | Gloss | Status |
| --- | --- | --- |
| `0058` (`.team/adr/0058-ctl-01-base-policy-family.md`) | Base ordering policy family: damped survival-weighted base-stock | ACCEPTED |
| `0060` (`.team/adr/0060-ctl-03-fractile-determination.md`) | How the target service fractile (`alpha`) is chosen | ACCEPTED |
| `0061` (`.team/adr/0061-ctl-04-rollout-horizon-and-terminal-value.md`) | Rollout look-ahead horizon and how the tail beyond it is valued | ACCEPTED |
| `0112` (`.team/adr/0112-x-11-mwf-delivery-base-case.md`) | Base-case delivery cadence is Monday/Wednesday/Friday with a 1-day lead time | ACCEPTED |
| `0114` (`.team/adr/0114-order-schedule-api.md`) | The `OrderSchedule` type/API (`can_order`, `protection_days`) | ACCEPTED |
| `0117` (`.team/adr/0117-studio-autopilot-mode.md`) | Studio autopilot: an automated act-loop over the damped-survival-weighted / rollout policies | ACCEPTED |

### Economics / experiment design

| ADR | Gloss | Status |
| --- | --- | --- |
| `0064` (`.team/adr/0064-sim-01-profit-accounting.md`) | How daily profit is accounted (margin, waste cost, stockout penalty) | ACCEPTED |
| `0069` (`.team/adr/0069-voi-01-voi-metric-definition.md`) | Definition of the value-of-information metric this project is named for | ACCEPTED |
| `0070` (`.team/adr/0070-voi-02-misspecification-and-honesty-arms.md`) | How VOI experiments handle a deliberately misspecified model arm | ACCEPTED |
| `0071` (`.team/adr/0071-voi-03-statistical-reporting-standard.md`) | Statistical reporting standard for VOI results (uncertainty, not point estimates alone) | ACCEPTED |
| `0104` (`.team/adr/0104-audit-remediation-defaults.md`) | Audit-driven default fixes: case rounding, shipment defaults, uncalibrated profit costs flagged explicitly | ACCEPTED |

### Studio / engineering

| ADR | Gloss | Status |
| --- | --- | --- |
| `0119` (`.team/adr/0119-rust-compute-kernel-python-host.md`) | Simulation compute moved to a Rust kernel (`voi_core`), Python remains host/citeable | ACCEPTED |
| `0120` (`.team/adr/0120-studio-wasm-adapter-third-host.md`) | Studio gains a `wasm` adapter (the Rust kernel compiled to WebAssembly) alongside Pyodide | ACCEPTED |
| `0122` (`.team/adr/0122-studio-episode-horizon-90.md`) | One studio episode runs for 90 days | ACCEPTED |
| `0126` (`.team/adr/0126-wasm-rich-filterobs-particle-belief.md`) | Wasm engine's belief is exported straight from the particle bank's posterior, RichObs-shaped | ACCEPTED |

## Caveats

- This index is **curated, not exhaustive**. The repository's full ADR log
  (`.team/adr/INDEX.md`) currently runs past 150 entries, including scenario-definition,
  filter-numerics, and packaging decisions not surfaced here because they don't map directly
  to a topic this site explains.
- Status can change. Two ADRs already superseded a T-150-era predecessor apiece in this list's
  own history (0144 supersedes 0138 and 0141); always check `.team/adr/INDEX.md`'s status
  column rather than trusting a cached belief about what's current — including this page's own
  table, if enough time has passed since 2026-08-23.
- A handful of ADRs cited above (e.g. 0033, 0017) are themselves not listed in the tables
  because their titles or content use retired vocabulary (arrival "age", "age at receipt")
  that ADR 0144 explicitly records as dead in the production code, even though their
  `INDEX.md` status is still ACCEPTED — an ADR's acceptance status describes the decision it
  records, not whether every word in its title survived later renaming.
- ADRs describe *decisions*, not current line numbers — always confirm an implementation claim
  against the live code (as every other page on this site does), not against an ADR's own
  code citations, which can drift out of date after the ADR is accepted.
