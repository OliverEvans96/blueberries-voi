# T-140 QA — test map (RED criterion → test)

| AC | Criterion | Test |
|----|-----------|------|
| AC-1 | Gamma arrival exports; no `f2a_transit_uncertainty_sd` | `t140_arrival_gamma::unified_arrival_exports_and_params_cleanup`, `birth_f_units_gamma_spreads_at_fixed_lambda` |
| AC-2 | Calendar pack_date | `t140_arrival_gamma::arrival_meta_emits_calendar_pack_date_not_rounded_tau` |
| AC-3 | No `mix_arrival_f` | `t140_arrival_gamma::mix_arrival_f_removed_from_unit_pf` |
| AC-4 | Thermal fleet φ̄ | `t140_arrival_gamma::shipments_thermal_phi_bar_non_degenerate` |
| AC-6 | F3 gamma birth | `t140_arrival_gamma::unit_pf_f3_uses_gamma_birth_path` |
| AC-7 | Python/TS drop f2a slider | `test_arrival_priors_no_f2a_constant`, web scenario tests (implement shard) |
| AC-8 | count_bias guard | existing `lgtin_upc_ac12` (post-implement) |
| AC-9 | Notebook 14 source | grep `calendar` + `thermal` in `notebook_14_source.md` |

RED command:

```bash
cargo test -p voi_core t140_arrival_gamma -- --nocapture
```

Expected: **FAIL** until implement lands.
