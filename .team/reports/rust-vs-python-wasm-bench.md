# Rust vs Python / WASM compute matrix (T-108)

Informational; not a CI gate. Machine knobs: `OMP_NUM_THREADS=1`, Python 3.11.13, x86_64.
Git SHA at run: see `outputs/bench_compute_matrix.json` (gitignored).

**Rust `run_voi_crn_cell` is a simplified closed-loop (constant order, no Abdella / full filter ladder).** Do not treat rust-pyo3 smoke VOI ~0.1 ms as a like-for-like speedup of the Python 7-scenario CRN (~0.48 s). `day_step` with injected demand **is** the same kernel shape.

| Use case | py-native | rust-pyo3 | pyodide | wasm |
| --- | --- | --- | --- | --- |
| Single day, physics (`day_step`, injected demand, 50 reps) | mean **0.273 ms** | mean **0.108 ms** (~2.5×) | n/a (browser) | n/a (build `./scripts/build-wasm.sh`) |
| Smoke CRN cell (Python: 7 scenarios, burn=1 score=2 N=16) | mean **0.48 s** | simplified kernel **~0.1 ms** (not equivalent work) | n/a | n/a |
| Cold start / `act(rollout)` / `step_n` | see T-106 baseline | not yet timed at EngineSession parity | n/a | worker RPC exists; pkg is local-build |

Host crossings: `day_step` and `run_voi_crn_cell` are **one FFI** when `BLUEBERRIES_VOI_BACKEND=rust`.

## How to re-run

```bash
maturin develop --manifest-path crates/voi_py/pyproject.toml
PYTHONPATH=src python experiments/bench_compute_matrix.py
./scripts/build-wasm.sh   # then Vite VITE_ENGINE_ADAPTER=wasm
```

Pre-port Python baseline: `.team/reports/python-compute-baseline-T-106.md` (smoke VOI 1.44 s including parquet parse; this matrix smoke is 0.48 s with `smoke_cool_shipments`).
