# GSIN/UPC investigation data

Machine-generated inputs for `notebooks/14_gsin_vs_upc_filter_accuracy.ipynb`.

| File | Produced by |
|------|-------------|
| `gsin_upc_pre_t141.json` | Pre–T-141 baseline: copy of `gsin_upc_after.json` from `team/T-140/implement` (shared-δ interval spoilage, ADR 0137) |
| `gsin_upc_before.json` | Legacy alias from T-137 harness (retained for notebook diff labels) |
| `gsin_upc_after.json` | `cargo run -p voi_core --release --example gsin_upc_diag -- <path>` on T-141 (independent aging + PB filter, ADR 0143) |
| `voi_profits_before.json` | `run_voi_crn_cell`, `n_burn=2 n_score=30 filter_n=24`, seeds 42/7/101/2024, on `team/T-137/implement` |
| `voi_profits_after.json` | same budgets on this branch |

Regenerate the "after" files with `experiments/regen_gsin_upc_data.sh`.
