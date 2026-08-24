# Modal batch map (T-155 / T-156)

See ADR 0145. Production nb13 / nb14 / nb15 / nb16 runs are intended for **Modal**
from the notebook kernel via ``blueberries_voi.experiments.modal_dispatch.run_batch``;
``local_runner.py`` remains for gsin shards, CI-sized smoke tests, and
``BATCH_MODE="local"``.

## Build artifacts (once per code change)

From the repo root, on Python **3.11**:

```bash
# PyO3 extension wheel (Modal does not compile Rust)
uv sync --python 3.11
uv run maturin build --release -m crates/voi_py/Cargo.toml -o dist/wheel
# Wheel: dist/wheel/blueberries_voi_core-*.whl; Python package copied from src/

# gsin_upc_diag shard binary
cargo build -p voi_core --release --example gsin_upc_diag
```

## Local (no Modal account)

```bash
export BLUEBERRIES_VOI_BACKEND=rust
uv run maturin develop --release -m crates/voi_py/Cargo.toml
uv run python experiments/modal/local_runner.py nb13 /tmp/nb13_rows.json --days 30
uv run python experiments/modal/local_runner.py gsin /tmp/gsin_upc.json
```

Set `GSIN_UPC_DIAG_BIN` if the release example is not at
`target/release/examples/gsin_upc_diag`.

## Notebook kernel (recommended)

```python
from blueberries_voi.experiments.modal_dispatch import run_batch

BATCH_MODE = "local"  # or "modal" after wheel + modal login
SMOKE = True  # shrink grids for plumbing

rows = run_batch("voi_profit", BATCH_MODE, smoke=SMOKE, seeds=(42,), channels=[...])
gsin_df = run_batch("gsin", BATCH_MODE, smoke=SMOKE)
rollout_rows = run_batch("rollout_eval", BATCH_MODE, smoke=SMOKE, seeds=(42,), arms=("sw",))
```

## Modal CLI (optional)

```bash
pip install 'blueberries-voi[modal]'   # or: uv sync --extra modal
export BLUEBERRIES_VOI_WHEEL=dist/wheel  # relative paths resolve from repo root (not notebook cwd)
modal run experiments/modal/app.py::nb13 --out experiments/data/nb13_channel_rows.json
modal run experiments/modal/app.py::gsin --out gsin_upc_sharded.json
```

Image contents: Debian slim, `numpy`/`scipy`/`pyarrow`, copied Python package,
pre-built `_core` wheel, vendored `data/` (abdella + freshnet), copied
`gsin_upc_diag` binary. CPU only; timeouts 600s (nb13 / voi_profit) / 300s (gsin)
/ 900s (rollout_eval).

## Job grain

| Workload | Parallel axis | Sequential axis |
|----------|---------------|-----------------|
| Notebook 13 channel factorial | `(seed, channel)` × 12 combos × seeds | days within seed |
| `gsin_upc_diag` | `(regime, seed)` × 4 × 12 | truth days; 6 masks replayed per shard |
| VOI profit (nb15) | `(seed, ObsChannels)` | burn + scored `act()` days |
| Rollout bakeoff (nb16) | `(seed, arm, alpha)` | burn + scored episode |

Notebooks load results from the kernel session (DataFrame), not committed JSON.
Optional ``out_path`` writes gitignored cache under ``outputs/``.

## Preliminary notebooks (T-157)

| Notebook | Batch jobs | Notes |
|----------|------------|-------|
| ``notebooks/17_prelim_channel_ladder.ipynb`` | ``gsin`` (``gsin_cells=[(2,0)]``), ``voi_profit`` | P0/P1/F2a/F3, seed 42, ``n_burn=2`` ``n_score=5``, oracle row |
| ``notebooks/18_prelim_rollout_vs_sw.ipynb`` | ``rollout_eval`` | Loads ``outputs/sw_alpha_bo.json``; paired sw+rollout at α=0.9, CI budgets |

Set ``BATCH_MODE="local"`` for plumbing without Modal; build wheel + ``modal login`` for production.
