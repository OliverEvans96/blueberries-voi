# Modal batch map (T-155)

See ADR 0145. Production nb13 runs are intended for **Modal** only; `local_runner.py`
remains for gsin shards and CI-sized smoke tests.

## Build artifacts (once per code change)

From the repo root, on Python **3.11**:

```bash
# PyO3 extension wheel (Modal does not compile Rust)
uv sync --extra rust --extra modal --extra data --python 3.11
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

## Modal

```bash
pip install 'blueberries-voi[modal]'   # or: uv sync --extra modal
export BLUEBERRIES_VOI_WHEEL=dist/wheel  # directory with the .whl
# T-150: 36-channel factorial + 3 F3 jobs; writes summary + *_shards.json (per-day rows)
modal run experiments/modal/app.py::nb13 --out experiments/data/nb13_channel_rows.json
modal run experiments/modal/app.py::gsin --out gsin_upc_sharded.json
```

Image contents: Debian slim, `numpy`/`scipy`/`pyarrow`, copied Python package,
pre-built `_core` wheel, vendored `data/` (abdella + freshnet), copied
`gsin_upc_diag` binary. CPU only; timeouts 600s (nb13) / 300s (gsin).

## Job grain

| Workload | Parallel axis | Sequential axis |
|----------|---------------|-----------------|
| Notebook 13 channel factorial | `(seed, channel)` × 12 combos × 3 seeds | days within seed |
| `gsin_upc_diag` | `(regime, seed)` × 4 × 12 | truth days; 6 masks replayed per shard |

Notebook 14 JSON/plot cells are **not** Modal targets.
