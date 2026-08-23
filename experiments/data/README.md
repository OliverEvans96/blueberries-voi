# GSIN/UPC investigation data

Machine-generated inputs for `notebooks/14_gsin_vs_upc_filter_accuracy.ipynb`.

## Epoch ladder

Four code tips, oldest first. Each file is the same diagnostic at a different epoch.

| File | Epoch | Spoilage model | Rows |
|------|-------|----------------|------|
| `gsin_upc_before.json` | `team/T-137/implement`, pre-ADR-0137 | binomial waste; GSIN likelihood degenerate (the bug) | 18 |
| `gsin_upc_pre_t141.json` | ADR 0137 | shared-δ interval constraint | 18 |
| `gsin_upc_t140.json` | `team/T-140/implement`, ADR 0141 | shared-δ interval; unified gamma **arrival** | 24 |
| `gsin_upc_after.json` | `team/T-141/implement`, ADR 0143 | **independent per-unit aging** + Poisson-binomial | 24 |

**T-150 (ADR 0144):** `voi_profits_after.json` was regenerated under damped base-stock
(`n_rollout_paths=0`). `gsin_upc_after.json` was **not** regenerated (same T-141 spoilage
epoch). Filter-accuracy MAE for the new arrival law is `nb13_channel_rows.json` /
`nb13_channel_rows_shards.json` from Modal run `ap-n9eIOGAYfnAVTUHuGyfsjw` on a T-150 wheel.

The two oldest files predate the *Thermal fleet* fixture and carry three regimes.

**`gsin_upc_pre_t141.json` is not a run of the T-140 parent harness.** It is byte-identical
to the ADR 0137-era `gsin_upc_after.json` (commit `a332d26`) — three regimes, no thermal
fixture, generated two tickets before T-140. The genuine T-140 baseline is
`gsin_upc_t140.json`, regenerated at that tip with the corrected harness.

## Harness correction

The T-138 rewrite of `gsin_upc_diag` reintroduced, in the **measurement** code, the fixed
`units_per_lot` partition that ADR 0137 had removed from the filter, and read ESS back off
`bank.weights` *after* the step's resample — where they are uniform by construction.

Consequences for any file regenerated between T-138 and this correction (including the
shipped T-141 verify regen):

- `lot_count_mae` and `lot_mean_f_mae` chunk the particle row into 15-unit blocks while
  deliveries are 44 units. The numbers are unrelated to real lot boundaries.
- `ess` is exactly `N` (200.0) on every rung.

`gsin_upc_t140.json` and `gsin_upc_after.json` here are both regenerated with the corrected
harness, which reads `bank.lot_offsets` and `StepDiagnostics.ess`.

## Closed loop

| File | Produced by |
|------|-------------|
| `voi_profits_before.json` | `run_voi_crn_cell`, `n_burn=2 n_score=30 filter_n=24`, seeds 42/7/101/2024, on `team/T-137/implement` |
| `voi_profits_after.json` | same budgets on this branch |

## Regenerating

```bash
experiments/regen_gsin_upc_data.sh                              # belief metrics (~17 min)
uv run --python 3.11 python experiments/regen_voi_profits.py    # §4 closed loop
```

`regen_voi_profits.py` needs the PyO3 kernel:
`maturin develop --release -m crates/voi_py/Cargo.toml`.

Under the Poisson-binomial filter the diagnostic is a ~17 minute release run (≈20× the
pre-ADR-0143 cost). `crates/voi_core/tests/gsin_upc_ac12.rs` shells out to it, so both of
its gates share one invocation.

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
