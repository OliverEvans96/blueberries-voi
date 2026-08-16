# T-TAU-RETIRE — Retire τ / Weibull; complete f-native wire

## Context

ADR [0130](../adr/0130-f-native-unit-pf-wire.md) shipped the f-native unit particle filter
(`L×U` internal grid; `f_grid` / `f_marginals` / `lot_counts` on the wire). Production still
carries legacy τ paths: cohort `particle_filter`, Weibull effective inventory, wire fields
`age_at_receipt` / `live_lots[].tau`, and F2/F2a birth drivers that mis-wire τ instead of native
`f`.

ADR [0131](../adr/0131-f-native-wire-tau-retirement.md) locks wire renames, f-native birth,
MVP effective inventory (\(\tilde I = \sum n_\ell \mathbb{E}[f_\ell] + \text{pipeline}\)),
module deletions, and `picking_weights_f` in the unit likelihood. Explainer
[§8](../docs/f-native-unit-pf-explainer.md) documents effective inventory for readers.

**Base branch:** `team/feature-c2-a-f-native/implement` (unit PF, `DEFAULT_L_DIM = 10`).

## Acceptance criteria

### AC-wire — F-native wire fields

- [ ] Snapshot / RPC belief exports **`lot_counts`**, **`f_marginals`**, **`f_grid`** only — no
      `age_marginals` or `tau_grid` on production wire paths (`belief_flat_from_unit_bank`,
      Python `flatten_f_belief`, wasm snapshot).
- [ ] Observed receipt freshness on the wire is **`f_at_receipt`** (`f ∈ [0, 1]`), not
      `age_at_receipt`. `ObsMask` / scenario ladder masks use the renamed field; F2 presents
      `f_at_receipt` when unmasked.
- [ ] Truth overlay **`live_lots[]`** entries expose **`mean_f`** (mean alive-unit freshness per
      lot), not **`tau`**. Filter posterior remains on `f_marginals`; `live_lots` is physics-only.
- [ ] `rg 'age_at_receipt|"tau"' crates/voi_core/src/session.rs web/src/engine/ packaging/wasm/`
      on wire serialization paths returns no production-field matches (private τ in shipments OK).

### AC-birth — F-native delivery birth

- [ ] Delivery cohort birth calls `shipments::delivery_birth_f` (or equivalent) in session, VOI,
      and unit-PF filter step — **F2** Dirac from receipt `f`, **F2a** Gaussian on pack-date transit
      age (SD = `f2a_transit_uncertainty_sd`, default **0.75** τ-days) mapped to `f`, **P0**
      mixed shipment prior with Q10 **private** inside `shipments.rs`.
- [ ] F2/F2a driver bug fixed: births are not τ=0 / mis-wired cohort paths; unit PF and physics
      agree on birth `f` for the same CRN day (session tests / golden parity).
- [ ] After birth, inventory advances only via **gamma aging on `f`** — no in-store τ learning
      (FIL-11 / ADR 0105 spirit, f coordinates).

### AC-effective — Effective inventory MVP

- [ ] Production ordering uses **`effective_inventory_f_belief`** / **`damped_sw_order_f_belief`**
      (Rust), **`effective_inventory_f_belief`** on **`FreshShelfBelief`** (Python), and
      **`effectiveInventoryFromFlatBelief`** (web) only.
- [ ] **`effective_inventory_belief`**, **`damped_sw_order_belief`**, and belief-path
      **`survivalWeightedInventory`** are **deleted** (Rust `policy.rs`, Python τ belief helpers,
      `web/src/engine/projector.ts` belief `effective_inv`).
- [ ] \(\tilde I = \sum_\ell n_\ell \sum_k p_{\ell k} f_k + q_{\mathrm{pipe}} f_{\mathrm{pipe}}\)
      — unit test in Rust `policy.rs` and Python `belief.py` matches hand computation.
- [ ] `rg 'effective_inventory_belief|survivalWeightedInventory' src/ crates/voi_core/src/policy.rs
      web/src/engine/projector.ts` returns no matches on belief-driven ordering paths.

### AC-picking — F-native unit likelihood weights

- [ ] `sequential_kernel_path_logprob` uses **`picking_weights_f`** on raw unit `f` values — no
      `f_to_age` / τ picking bridge in the unit likelihood hot path.
- [ ] Ground-truth `pick_units_f` and unit likelihoods share the same sequential WOR kernel
      (existing parity tests updated if needed).

### AC-rust-delete — Legacy Rust modules removed

- [ ] `crates/voi_core/src/particle_filter.rs`, `day_step_legacy.rs`, and `exact_ll.rs` are
      **absent**; `lib.rs` does not export `filter_step`, `ParticleBank` (cohort), or
      `log_p_sales_waste_given_ages` from deleted modules.
- [ ] `belief_flat` τ flatteners (`age_marginals` production path) deleted; unit-bank flatteners
      remain.
- [ ] `cargo test -p voi_core` passes.

### AC-python — FreshShelfBelief promoted; τ production paths deleted

- [ ] **`FreshShelfBelief`** is the production belief type for closed-loop / VOI / viz host paths;
      τ **`ShelfBelief`** / `effective_inventory` (Weibull) removed from production imports.
- [ ] Production modules **`age_likelihood`** τ update paths, cohort **`particle/`** filter, and
      τ **`arrival_priors`** code used only by deleted filter are removed or quarantined to
      `experiments/` only.
- [ ] `sim/`, bakeoff, and `viz/` imports migrated to f-native APIs; failing tests rewritten
      (not skipped).

### AC-web — F-only studio

- [ ] Weibull **survival chart** and **β slider** removed from studio UI.
- [ ] Legacy projector shims (`isLegacyFlatBelief`, τ mock sim ordering) removed; charts and
      types are f-only.
- [ ] `cd web && npm test` passes.

### AC-goldens — Wire goldens regenerated

- [ ] Rust / Python / wasm wire goldens updated for `f_at_receipt`, `mean_f`, and f-only belief
      exports; no stale `age_at_receipt` / `tau` keys in checked-in golden fixtures.

### AC-verify — CI parity (verifier)

- [ ] On **Python 3.11** (repo pin), CI-identical gates pass:
      ```bash
      pip install -e ".[dev]"
      ruff check .
      ruff format --check .
      mypy src tests
      pytest -n auto --cov=blueberries_voi --cov-branch \
        --cov-report=term-missing --cov-report=xml --cov-fail-under=80
      ```
- [ ] `cargo test -p voi_core` passes (Rust workspace tests).
- [ ] Grep hot paths: no `effective_inventory_belief`, no `survivalWeightedInventory` on
      belief-driven `effective_inv`, no production `particle_filter` / `exact_ll` imports on
      closed-loop paths.

## Out of scope

- Precomputed gamma first-passage \(w(f_k)\) lookup (ADR 0131 v2 — follow-up ticket).
- Deleting **`experiments/`** or bakeoff-history Python that references τ for one-off reports.
- Editing live `.github/workflows/` (human sync if packaging draft changes).

## References

- ADR [0131](../adr/0131-f-native-wire-tau-retirement.md)
- Explainer [§8 Effective inventory](../docs/f-native-unit-pf-explainer.md)
- Plan: remove τ / Weibull f-native completion
