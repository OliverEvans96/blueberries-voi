# GSIN/UPC investigation data

Machine-generated inputs for `notebooks/14_gsin_vs_upc_filter_accuracy.ipynb`.

| File | Produced by |
|------|-------------|
| `gsin_upc_before.json` | `cargo run -p voi_core --release --example gsin_upc_diag -- <path>` on `team/T-137/implement` (pre-ADR-0137), with the example's baseline-API variant |
| `gsin_upc_after.json` | same example on this branch |
| `voi_profits_before.json` | `run_voi_crn_cell`, `n_burn=2 n_score=30 filter_n=24`, seeds 42/7/101/2024, on `team/T-137/implement` |
| `voi_profits_after.json` | same budgets on this branch |

Regenerate the "after" files with:

```bash
experiments/regen_gsin_upc_data.sh                              # belief metrics
uv run --python 3.11 python experiments/regen_voi_profits.py    # §4 closed loop
```

`regen_voi_profits.py` needs the PyO3 kernel:
`maturin develop --release -m crates/voi_py/Cargo.toml`.

## Regime coverage

The diag harness runs **four** fleet regimes as of T-140 (ADR 0141):

| Regime | Varies | Ladder step it exercises |
|--------|--------|--------------------------|
| Homogeneous fleet, overlapping lots | nothing (one trace) | neither |
| Heterogeneous fleet, overlapping lots | transit **duration** | F1 → F2 (pack date) |
| Heterogeneous fleet, deep shelf | transit **duration**, deeper stock | F1 → F2 (pack date) |
| Thermal fleet, overlapping lots | transit **temperature** (duration fixed) | F2 → F3 (temp trace) |

`gsin_upc_before.json` predates the thermal fixture and carries only the first three, so the
notebook restricts every before/after panel to the shared set. Regimes are addressed by name
there, not by position.
