# T-139 RED criterion → test map

| AC | Criterion | Test(s) | Module |
|----|-----------|---------|--------|
| AC-1 | F3 in AC-12 drift guard | `gsin_upc_homogeneous_fleet_count_bias_drift_guard` | `crates/voi_core/tests/gsin_upc_ac12.rs` |
| AC-2 | F3 root-cause documented | `f3_dispersion_count_bias_root_cause_temperature_birth_center` | `gsin_upc_ac12.rs` |
| AC-3 | Filter birth mass conservation | `filter_birth_alive_mass_matches_arrivals_under_dispersion` | `t134_arrival_f.rs` |
| AC-4 | Session lot_counts tracking | `session_lot_counts_track_arrivals_minus_decay` | `t134_arrival_f.rs` |
| AC-5 | Contrast hook exported | `contrast_spoilage_weight_exported_and_inert_at_sd_zero` | `t134_arrival_f.rs` |
| AC-6 | sd=0 VOI CRN parity | `test_voi_crn_sd_zero_matches_t138_baseline` | `tests/test_t139_voi_crn_sd0.py` |
| AC-7 | Python cov ≥80% | `tests/test_filter_belief.py` | `filter/belief.py` |
