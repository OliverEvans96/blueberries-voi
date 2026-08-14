# Rust vs Python / WASM compute matrix (T-109)

Informational. RNG is independent PCG (**not** NumPy-identical). Citeable VOI stays Python.

T-109 ports CRN **structure**: Q10 shipment ages, SW+rollout, scenario masks (P0 waste unobserved), shared physics seed, SIM-01 scored profit. A short smoke cell (burn=1, score=2) can land near −6 on Rust because delivery is applied **after** sales on the arrival day—the same MOD-12 order as Python—not because the kernel is a no-op stub.

| Use case | py-native | rust-pyo3 | pyodide | wasm (Node harness) |
| --- | --- | --- | --- | --- |
| Smoke CRN, `smoke_cool` shipments, burn=1 score=2, N=16, H=2, paths=1 | ~0.85 s (this machine) | ~8 ms **debug** PyO3; **not** a citeable speedup; profits ≠ Python | n/a | n/a (session RPC only) |
| Cold start | T-106 | maturin import | n/a in Node (`loadPyodide` not embedded) | ~0.044 s |
| `step` | T-106 Python `EngineSession` | `PyEngineSession` exists; Python `EngineSession` class still Python | n/a | mean ~0.7 ms (5 reps; first slower) |
| `step_n(7)` one crossing | T-106 | same caveat | n/a | mean ~1.1 ms |
| `act(rollout)` | T-106 | same caveat | n/a | mean ~0.08 ms |

**Still n/a:** Node Pyodide column; wasm VOI cell; Abdella parquet on the Rust path (`shipments=None` stays Python); FastAPI / viz / pyodide packaging tests (not ported).

## How to re-run

```bash
cargo test -p voi_core
maturin develop --manifest-path crates/voi_py/Cargo.toml
BLUEBERRIES_VOI_BACKEND=python PYTHONPATH=src python experiments/bench_compute_matrix.py
BLUEBERRIES_VOI_BACKEND=rust PYTHONPATH=src python experiments/bench_compute_matrix.py
./scripts/build-wasm.sh
node experiments/bench_compute_browser.mjs
```
