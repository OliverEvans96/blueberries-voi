# T-117 QA — RED map

Focused `cargo test -p voi_core` (2026-08-15): **21 failed**, 64 passed.
Focused `npx vitest run src/engine/projector.test.ts`: **18 passed** (heatmap-from-belief already true in projector).

## Coverage of acceptance criteria

- After arrivals, Snapshot `belief.age_marginals` under **F2** differs from **P0**; `live_lots` identical → `crates/voi_core/src/session.rs::f2_belief_differs_from_p0_live_lots_unchanged` — currently failing: both rungs still emit oracle one-hot from physics lots (`[0, 1, 0, 0]`).
- After arrivals, **F2a** age mass narrower than **P1** → `session.rs::f2a_age_mass_narrower_than_p1` — currently failing: both merged-age entropies are 0 (oracle Dirac).
- After positive waste, **P0** vs **P1** `belief.lot_counts` / `age_marginals` differ → `session.rs::p0_vs_p1_belief_differs_after_waste` — currently failing: Snapshot.belief is still `oracle_flat_belief` (identical across rungs).
- Uneven `sales_by` → **F1** posterior differs from **P1** → `session.rs::f1_vs_p1_belief_differs_after_uneven_sales` — currently failing: uniform/`oracle` age_marginals match (`0.25` grid).
- Catch-up mid-episode to F2 matches never-switched F2 (CRN) and is not P0/oracle → `session.rs::catch_up_f2_matches_never_switched_and_not_oracle` — currently failing: F2 Snapshot.belief equals P0 oracle ages. (Weight CRN vs never-switched already holds for totals-only.)
- Invalid ids `P2` and `B-state` error like Python `mask_for` → `obs.rs::mask_for_p2_and_b_state_error_like_python` — currently failing: stub `mask_for` returns empty `Ok` mask. Also `session.rs::set_obs_scenario_rejects_p2_and_b_state` (and existing `set_obs_scenario_invalid_id_errors`) — **passing** on session `validate_scenario`.
- `cargo test -p voi_core` covers mask_for / FilterObs / birth / `belief_flat` / session wiring:
  - `obs::tests::mask_for_p0_has_arrivals_and_sales_total_only` — failing: empty stub mask (`arrivals` false).
  - `obs::tests::mask_for_p1_adds_waste_total` — failing: stub.
  - `obs::tests::mask_for_f1_adds_sales_by_lot_and_lot_ids_live` — failing: stub.
  - `obs::tests::mask_for_f1s_adds_waste_by_lot_and_lot_ids_live` — failing: stub.
  - `obs::tests::mask_for_f2a_is_p1_plus_pack_date` — failing: stub.
  - `obs::tests::mask_for_f2_has_maps_age_at_receipt_and_lot_ids` — failing: stub.
  - `obs::tests::apply_p0_omits_waste_never_invents_zero` — failing: `apply` returns `FilterObs::default()` (arrivals 0).
  - `obs::tests::apply_f2_keeps_maps_and_age_at_receipt` — failing: `apply` stub.
  - `particle_filter::tests::filter_step_f2_births_dirac_on_age_at_receipt` — failing: birth τ=0, expected 2.25.
  - `particle_filter::tests::filter_step_f2a_gaussian_birth_mean_calendar_sd_075` — failing: mean 0 not 2, SD 0.
  - `particle_filter::tests::filter_step_p0_birth_not_always_zero` — failing: all births τ=0.
  - `particle_filter::tests::filter_step_lot_map_sales_by_changes_weights_vs_totals` — failing: L1 weight distance 0 (maps ignored).
  - `belief_flat::tests::empty_bank_pads_l_by_k_zero_counts` — failing: stub `L=0` / empty arrays.
  - `belief_flat::tests::weighted_lot_counts_and_age_histogram` — failing: stub flatten.
  - `belief_flat::tests::truncates_or_pads_to_l` — failing: stub flatten.
- Vitest projector heatmap **density** from `snapshot.belief` (not live_lots n/τ); belief change moves density; live_lots change does not rewrite age mass (count axis may grow) → `web/src/engine/projector.test.ts`:
  - `applySnapshot density follows belief, not live_lots n/τ` — **passing** (already `beliefGridFromFlat(flatBelief, liveLots)`).
  - `patchEngineState: changing belief with fixed live_lots changes density` — **passing**.
  - `patchEngineState: changing live_lots with fixed belief does not rewrite age mass` — **passing**.

## Not covered by tests

- Do not edit `.github/workflows/` — process; verify by review.
- Zero Python production edits — process; verify by diff (only `crates/voi_py` FilterObs `..Default::default()` so the rich struct compiles).
- Abdella parquet / SCN-P2 chips / `mean_field_update` — out of scope.
