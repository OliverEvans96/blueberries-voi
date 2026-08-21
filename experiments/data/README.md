# GSIN/UPC investigation data

Machine-generated inputs for `notebooks/14_gsin_vs_upc_filter_accuracy.ipynb`.

| File | Produced by |
|------|-------------|
| `gsin_upc_before.json` | `cargo run -p voi_core --release --example gsin_upc_diag -- <path>` on `team/T-137/implement` (pre-ADR-0137), with the example's baseline-API variant |
| `gsin_upc_after.json` | same example on this branch |
| `voi_profits_before.json` | `run_voi_crn_cell`, `n_burn=2 n_score=30 filter_n=24`, seeds 42/7/101/2024, on `team/T-137/implement` |
| `voi_profits_after.json` | same budgets on this branch |

Regenerate the "after" files with `experiments/regen_gsin_upc_data.sh`.
