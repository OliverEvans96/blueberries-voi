# Architecture Decision Records

Imported from Afresh blog-post decision board export (`ADR-EXPORT.md`), 2026-08-12.

- Authority: Oliver — explicit per-card confirmation on the scoping board
- Source: `notes/claude/architecture/decisions/*.md` → `ADR-EXPORT.md`
- Domain ADRs: **0001–0076** (75 accepted, 1 superseded)
- Repo tooling ADR: **[0077](./0077-uv-src-layout-agent-dev-team.md)** (renumbered from 0001 on import to preserve domain numbering)
- M1 settle / defer (2026-08-12): **[0078](./0078-x-13-gate-0.md)–[0085](./0085-pyarrow-abdella-parquet.md)** (FIL-13/15 accepted after bakeoff; pyarrow for Abdella)
- M1.5 architecture lock (2026-08-12): **[0086](./0086-m15-richobs-unobserved-masks.md)–[0089](./0089-m15-dynamic-l-sliding-window-fallback.md)** (RichObs/masks, MC LL, generative Stage C, L fallback)
- FIL-11 Stage C / FIL-04 evidence (additive): **[0090](./0090-fil11-stage-c-sequential-wor-pmf-exact-vs-mf.md)** (`sequential_wor_pmf`; exact joint vs mean-field; does not replace M1.5 Stage C)
- Production mean-field settle (2026-08-12): **[0091](./0091-fil13-production-mean-field.md)** (FIL-13=B / FIL-04→C; supersedes 0082/0089 production defaults; 0049→C; 0057 historical)
- M2 controller lock (2026-08-12): **[0092](./0092-controller-belief-api.md)–[0093](./0093-day-profit-helper.md)** (`ShelfBelief` / MF marginals; `sim/profit.py` SIM-01 extract)
- M3 VOI lock (2026-08-12): **[0094](./0094-voi-package-layout.md)–[0096](./0096-voi-scenario-columns.md)** (`voi/` modules; CI smoke budgets; scenario columns)
- Repo tooling (2026-08-12): **[0097](./0097-pytest-xdist-for-verify-ci.md)** (pytest-xdist for verify/CI full-suite runs)
- Repo tooling (2026-08-13): **[0098](./0098-pytest-testmon-lfs-cache.md)** (pytest-testmon + Git LFS `.testmondata` seed)
- ENG-01 reopen dual-runtime (2026-08-12): **[0099](./0099-eng-01-dual-runtime-ap.md)–[0102](./0102-eng-01-api-asgi-session.md)** (A′ Pyodide prod + API dev; export; packaging; ASGI); **[0073](./0073-eng-01-browser-simulator-scope.md)** superseded
- M3 exact LL speedup (2026-08-12): **[0103](./0103-exact-faster-p1-f2a-likelihood.md)** (unique-particle MF dedup + NumPy sequential-WOR DP; no surrogate; no new runtime deps)
- Audit remediation lock (2026-08-12): **[0104](./0104-audit-remediation-defaults.md)** (nearest `case_round`; Abdella shipment defaults; uncalibrated `DEFAULT_PROFIT_COSTS`; VOI α-table gate; MF sweeps=5; bakeoff stubs non-citeable)
- ENG-01 dual-mode readiness (2026-08-13): **[0107](./0107-demo-hydrate-at-host-edges.md)–[0108](./0108-local-dual-mode-vite-wheel-cors.md)** (host-edge demo hydrate; Vite wheel/`wheelUrl`/CORS). Do **not** confuse with in-flight arrival-only ADR **0105–0106** on `team/T-067/architect`.
- CAL-01 calendar realism Wave 0 (2026-08-13): **[0109](./0109-x-11-mwf-delivery-base-case.md)–[0113](./0113-cal-01-track-ownership.md)** (MWF base case; calendar NB; OrderSchedule; FreshNet product; track ownership). **[0011](./0011-x-11-delivery-cadence-for-the-base-case.md)** and **[0031](./0031-mod-09-demand-model.md)** superseded. Do **not** confuse with in-flight arrival-only ADR **0105–0106**.
- ⚑ marks decisions made against the card recommendation

## Index

| ADR | Board ID | Title | Status |
| --- | --- | --- | --- |
| [0001](./0001-x-01-what-the-post-must-demonstrate.md) | `X-01` | What the post must demonstrate ⚑ | ACCEPTED |
| [0002](./0002-x-02-objective-denomination.md) | `X-02` | Objective denomination | ACCEPTED |
| [0003](./0003-x-03-date-pull-in-or-out.md) | `X-03` | Date pull in or out ⚑ | ACCEPTED |
| [0004](./0004-x-04-controller-action-space.md) | `X-04` | Controller action space ⚑ | ACCEPTED |
| [0005](./0005-x-05-knowledge-scenario-ladder-membership.md) | `X-05` | Knowledge scenario ladder — membership | SUPERSEDED |
| [0006](./0006-x-06-voi-sweep-axes.md) | `X-06` | VOI sweep axes ⚑ | ACCEPTED |
| [0007](./0007-x-07-scope-of-the-instance.md) | `X-07` | Scope of the instance | ACCEPTED |
| [0008](./0008-x-08-data-provenance.md) | `X-08` | Data provenance | ACCEPTED |
| [0009](./0009-x-09-language-and-stack.md) | `X-09` | Language and stack ⚑ | ACCEPTED |
| [0010](./0010-x-10-reproducibility-standard.md) | `X-10` | Reproducibility standard | ACCEPTED |
| [0011](./0011-x-11-delivery-cadence-for-the-base-case.md) | `X-11` | Delivery cadence for the base case ⚑ (daily) | SUPERSEDED BY 0109 |
| [0012](./0012-x-12-tripwire-if-the-headline-number-is-flat.md) | `X-12` | Tripwire if the headline number is flat ⚑ | ACCEPTED |
| [0013](./0013-scn-b-clair-perfect-foresight-oracle.md) | `SCN-B-clair` | Perfect foresight oracle ⚑ | ACCEPTED |
| [0014](./0014-scn-b-state-perfect-state-oracle.md) | `SCN-B-state` | Perfect state oracle | ACCEPTED |
| [0015](./0015-scn-f1-sunrise-partial-lot-id-at-pos.md) | `SCN-F1` | Sunrise partial — lot ID at POS | ACCEPTED |
| [0016](./0016-scn-f1s-lot-id-on-the-shrink-gun.md) | `SCN-F1s` | Lot ID on the shrink gun | ACCEPTED |
| [0017](./0017-scn-f2-sunrise-full-age-at-receipt.md) | `SCN-F2` | Sunrise full — age at receipt | ACCEPTED |
| [0018](./0018-scn-f2a-pack-date-on-the-supplier-asn.md) | `SCN-F2a` | Pack date on the supplier ASN | ACCEPTED |
| [0019](./0019-scn-f3-sunrise-plus-esl-markdown.md) | `SCN-F3` | Sunrise plus ESL markdown | ACCEPTED |
| [0020](./0020-scn-p0-books-only.md) | `SCN-P0` | Books only | ACCEPTED |
| [0021](./0021-scn-p1-shrink-gun.md) | `SCN-P1` | Shrink gun | ACCEPTED |
| [0022](./0022-scn-p2-instrumented-store.md) | `SCN-P2` | Instrumented store ⚑ | ACCEPTED |
| [0023](./0023-mod-01-unit-of-inventory-state.md) | `MOD-01` | Unit of inventory state ⚑ | ACCEPTED |
| [0024](./0024-mod-02-effective-age-dynamics.md) | `MOD-02` | Effective age dynamics | ACCEPTED |
| [0025](./0025-mod-03-in-store-temperature-treatment.md) | `MOD-03` | In-store temperature treatment ⚑ | ACCEPTED |
| [0026](./0026-mod-04-spoilage-law.md) | `MOD-04` | Spoilage law | ACCEPTED |
| [0027](./0027-mod-05-within-lot-heterogeneity.md) | `MOD-05` | Within-lot heterogeneity ⚑ | ACCEPTED |
| [0028](./0028-mod-06-clock-origin-and-left-truncation.md) | `MOD-06` | Clock origin and left-truncation | ACCEPTED |
| [0029](./0029-mod-07-picking-kernel-form.md) | `MOD-07` | Picking kernel form | ACCEPTED |
| [0030](./0030-mod-08-allocation-law.md) | `MOD-08` | Allocation law | ACCEPTED |
| [0031](./0031-mod-09-demand-model.md) | `MOD-09` | Demand model (i.i.d.) | SUPERSEDED BY 0110 |
| [0032](./0032-mod-10-unmet-demand.md) | `MOD-10` | Unmet demand | ACCEPTED |
| [0033](./0033-mod-11-arrival-age-distribution.md) | `MOD-11` | Arrival age distribution ⚑ | ACCEPTED |
| [0034](./0034-mod-12-within-day-order-of-operations.md) | `MOD-12` | Within-day order of operations | ACCEPTED |
| [0035](./0035-mod-13-bounding-the-number-of-live-cohorts.md) | `MOD-13` | Bounding the number of live cohorts ⚑ | ACCEPTED |
| [0036](./0036-mod-14-are-arrival-counts-observed-exactly.md) | `MOD-14` | Are arrival counts observed exactly ⚑ | ACCEPTED |
| [0037](./0037-mod-15-shrink-reporting-compliance.md) | `MOD-15` | Shrink reporting compliance ⚑ | ACCEPTED |
| [0038](./0038-mod-16-lots-per-delivery-below-the-scanning-rung.md) | `MOD-16` | Lots per delivery below the scanning rung ⚑ | ACCEPTED |
| [0039](./0039-mod-17-what-the-books-only-rung-actually-observes.md) | `MOD-17` | What the books-only rung actually observes ⚑ | ACCEPTED |
| [0040](./0040-mod-18-transit-model-parameterisation.md) | `MOD-18` | Transit model parameterisation | ACCEPTED |
| [0041](./0041-mod-19-t-ref-convention.md) | `MOD-19` | T_ref convention | ACCEPTED |
| [0042](./0042-mod-20-numeric-in-store-temperature.md) | `MOD-20` | Numeric in-store temperature ⚑ | ACCEPTED |
| [0043](./0043-mod-21-abdella-transit-sampling-frame.md) | `MOD-21` | Abdella transit sampling frame | ACCEPTED |
| [0044](./0044-mod-22-weibull-shape-under-x-08-revisit.md) | `MOD-22` | Weibull shape under X-08 revisit | ACCEPTED |
| [0045](./0045-mod-23-strawberry-logger-to-blueberry-substitution.md) | `MOD-23` | Strawberry-logger to blueberry substitution | ACCEPTED |
| [0046](./0046-fil-01-filter-family.md) | `FIL-01` | Filter family ⚑ | ACCEPTED |
| [0047](./0047-fil-02-what-is-sampled-versus-marginalised.md) | `FIL-02` | What is sampled versus marginalised | ACCEPTED |
| [0048](./0048-fil-03-arrival-age-discretisation.md) | `FIL-03` | Arrival-age discretisation ⚑ | ACCEPTED |
| [0049](./0049-fil-04-factorisation-of-age-across-cohorts.md) | `FIL-04` | Factorisation of age across cohorts (→ C via 0091) | SUPERSEDED BY 0091 |
| [0050](./0050-fil-05-particle-count-and-resampling.md) | `FIL-05` | Particle count and resampling | ACCEPTED |
| [0051](./0051-fil-06-handling-static-parameter-degeneracy.md) | `FIL-06` | Handling static-parameter degeneracy ⚑ | ACCEPTED |
| [0052](./0052-fil-07-where-parameter-inference-lives.md) | `FIL-07` | Where parameter inference lives | ACCEPTED |
| [0053](./0053-fil-08-observation-model-structure.md) | `FIL-08` | Observation model structure ⚑ | ACCEPTED |
| [0054](./0054-fil-09-reporting-lag-on-waste.md) | `FIL-09` | Reporting lag on waste | ACCEPTED |
| [0055](./0055-fil-10-proposal-distribution.md) | `FIL-10` | Proposal distribution | ACCEPTED |
| [0056](./0056-fil-11-how-we-know-the-filter-works.md) | `FIL-11` | How we know the filter works | ACCEPTED |
| [0057](./0057-fil-12-making-the-joint-age-posterior-tractable.md) | `FIL-12` | Making the joint age posterior tractable ⚑ | HISTORICAL (0091) |
| [0058](./0058-ctl-01-base-policy-family.md) | `CTL-01` | Base policy family ⚑ | ACCEPTED |
| [0059](./0059-ctl-02-depth-of-policy-improvement.md) | `CTL-02` | Depth of policy improvement | ACCEPTED |
| [0060](./0060-ctl-03-fractile-determination.md) | `CTL-03` | Fractile determination ⚑ | ACCEPTED |
| [0061](./0061-ctl-04-rollout-horizon-and-terminal-value.md) | `CTL-04` | Rollout horizon and terminal value | ACCEPTED |
| [0062](./0062-ctl-05-baseline-ladder.md) | `CTL-05` | Baseline ladder | ACCEPTED |
| [0063](./0063-ctl-06-optimality-certificate.md) | `CTL-06` | Optimality certificate | ACCEPTED |
| [0064](./0064-sim-01-profit-accounting.md) | `SIM-01` | Profit accounting | ACCEPTED |
| [0065](./0065-sim-02-outer-loop-crn-scope.md) | `SIM-02` | Outer-loop CRN scope | ACCEPTED |
| [0066](./0066-sim-03-episode-structure-and-burn-in.md) | `SIM-03` | Episode structure and burn-in | ACCEPTED |
| [0067](./0067-sim-04-ground-truth-instrumentation-contract.md) | `SIM-04` | Ground-truth instrumentation contract | ACCEPTED |
| [0068](./0068-sim-05-seed-and-experiment-addressing-scheme.md) | `SIM-05` | Seed and experiment addressing scheme | ACCEPTED |
| [0069](./0069-voi-01-voi-metric-definition.md) | `VOI-01` | VOI metric definition | ACCEPTED |
| [0070](./0070-voi-02-misspecification-and-honesty-arms.md) | `VOI-02` | Misspecification and honesty arms ⚑ | ACCEPTED |
| [0071](./0071-voi-03-statistical-reporting-standard.md) | `VOI-03` | Statistical reporting standard | ACCEPTED |
| [0072](./0072-voi-04-sweep-resolution.md) | `VOI-04` | Sweep resolution ⚑ | ACCEPTED |
| [0073](./0073-eng-01-browser-simulator-scope.md) | `ENG-01` | Browser simulator scope ⚑ (static only) | SUPERSEDED BY 0099 |
| [0074](./0074-eng-02-repo-and-module-layout.md) | `ENG-02` | Repo and module layout | ACCEPTED |
| [0075](./0075-eng-03-figure-and-plot-pipeline.md) | `ENG-03` | Figure and plot pipeline ⚑ | ACCEPTED |
| [0076](./0076-eng-04-test-and-validation-harness-scope.md) | `ENG-04` | Test and validation harness scope ⚑ | ACCEPTED |

| [0077](./0077-uv-src-layout-agent-dev-team.md) | *(repo)* | uv + src layout + agent-dev-team for simulation work | ACCEPTED |
| [0078](./0078-x-13-gate-0.md) | `X-13` | Gate 0 — both calculations before/alongside arrival generator | ACCEPTED |
| [0079](./0079-mod-25-numeric-picking-sigma.md) | `MOD-25` | Numeric picking-kernel σ = 0.5 + uniform sensitivity | ACCEPTED |
| [0080](./0080-mod-26-demand-case-shelf.md) | `MOD-26` | Demand μ=30, V/M=2, case 8 + sensitivity at 4 | ACCEPTED |
| [0081](./0081-fil-14-cohort-extinction.md) | `FIL-14` | Cohort extinct when n = 0 exactly | ACCEPTED |
| [0082](./0082-fil-13-tractability-bakeoff.md) | `FIL-13` | Tractability restore — full joint (E) at measured L | SUPERSEDED BY 0091 |
| [0083](./0083-fil-15-filter-numerics.md) | `FIL-15` | Filter numerics — K=8 on [0,8], N=2000, ESS=N/2 | ACCEPTED |
| [0084](./0084-runtime-deps-numpy-scipy-matplotlib.md) | *(repo)* | Runtime deps: numpy, scipy, matplotlib | ACCEPTED |
| [0085](./0085-pyarrow-abdella-parquet.md) | *(repo)* | pyarrow for Abdella parquet I/O | ACCEPTED |
| [0086](./0086-m15-richobs-unobserved-masks.md) | `FIL-08` (M1.5) | RichObs + UNOBSERVED + scenario masks | ACCEPTED |
| [0087](./0087-m15-mc-observation-likelihood.md) | `FIL-10` (M1.5) | MC observation likelihood from shared day_step | ACCEPTED |
| [0088](./0088-m15-stage-c-generative-check.md) | `FIL-11` (M1.5) | Stage C generative check vs day_step | ACCEPTED |
| [0089](./0089-m15-dynamic-l-sliding-window-fallback.md) | `FIL-13` (M1.5) | Dynamic L + joint→sliding_window fallback | SUPERSEDED BY 0091 |
| [0090](./0090-fil11-stage-c-sequential-wor-pmf-exact-vs-mf.md) | `FIL-11` / `FIL-04` evidence | Filter age likelihood (`sequential_wor_pmf`) — exact joint vs mean-field | ACCEPTED |
| [0091](./0091-fil13-production-mean-field.md) | `FIL-13` / `FIL-04` | Production RBPF age backend is mean-field (FIL-13=B); FIL-04 → C | ACCEPTED |
| [0092](./0092-controller-belief-api.md) | `CTL` / M2 | Controller belief API is ShelfBelief over MF marginals and oracle | ACCEPTED |
| [0093](./0093-day-profit-helper.md) | `SIM-01` (M2 extract) | Day profit helper lives in sim/profit.py (SIM-01 extract for CTL) | ACCEPTED |
| [0094](./0094-voi-package-layout.md) | `VOI` / M3 | VOI package layout and public API under `voi/` | ACCEPTED |
| [0095](./0095-voi-ci-smoke-budgets.md) | `VOI-04` / ENG-04 | M3 CI smoke budgets vs production VOI defaults | ACCEPTED |
| [0096](./0096-voi-scenario-columns.md) | `X-05` / `X-06` | M3 knowledge-scenario columns for the VOI sweep | ACCEPTED |
| [0097](./0097-pytest-xdist-for-verify-ci.md) | *(repo)* | pytest-xdist for verify/CI full-suite runs | ACCEPTED |
| [0098](./0098-pytest-testmon-lfs-cache.md) | *(repo)* | pytest-testmon + Git LFS `.testmondata` seed | ACCEPTED |
| [0099](./0099-eng-01-dual-runtime-ap.md) | `ENG-01` | Reopen: dual runtime A′ (Pyodide prod + API dev) | ACCEPTED |
| [0100](./0100-simulator-export-contract.md) | `ENG-01` | Simulator export: Snapshot / DayDelta / step_n | ACCEPTED |
| [0101](./0101-eng-01-packaging-pyodide-wheels.md) | `ENG-01` | Packaging: derived Abdella, extras, GH Release, Pyodide 314 | ACCEPTED |
| [0102](./0102-eng-01-api-asgi-session.md) | `ENG-01` | API host: ASGI sessions wrapping EngineSession | ACCEPTED |
| [0103](./0103-exact-faster-p1-f2a-likelihood.md) | *(repo)* / M3 compute | Exact-faster P1/F2a likelihood (unique-MF + NumPy DP) | ACCEPTED |
| [0104](./0104-audit-remediation-defaults.md) | *(repo audit)* | Audit remediation: case_round, Abdella defaults, costs, α gate, MF sweeps, bakeoff stubs | ACCEPTED |
| [0107](./0107-demo-hydrate-at-host-edges.md) | `ENG-01` | Demo hydrate shipments at API + Pyodide worker edges | ACCEPTED |
| [0108](./0108-local-dual-mode-vite-wheel-cors.md) | `ENG-01` | Local dual-mode: Vite wheel + worker, wheelUrl, CORS | ACCEPTED |
| [0109](./0109-x-11-mwf-delivery-base-case.md) | `X-11` / CAL-01 | MWF delivery base case (LT=1; order Sun/Tue/Thu) | ACCEPTED |
| [0110](./0110-mod-09-calendar-demand.md) | `MOD-09` / CAL-01 | Known NB with calendar DOW×week structure | ACCEPTED |
| [0111](./0111-order-schedule-api.md) | `CAL-A1` | OrderSchedule type/API (can_order / protection_days) | ACCEPTED |
| [0112](./0112-freshnet-derived-demand-product.md) | `CAL-B1` | FreshNet derived demand product + transferability | ACCEPTED |
| [0113](./0113-cal-01-track-ownership.md) | `CAL-01` | Track ownership + draw_demand(day=) shim | ACCEPTED |
