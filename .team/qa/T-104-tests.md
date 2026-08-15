# T-104 implement: Python tests mirrored into voi_core

| Python file | Rust location |
| --- | --- |
| tests/test_model.py | crates/voi_core/src/physics.rs + day_step.rs `#[cfg(test)]` |
| tests/test_sequential_wor_numpy.py | crates/voi_core/src/wor.rs |
| tests/test_age_likelihood.py (WOR/exact LL slice) | crates/voi_core/src/particle_filter.rs `exact_wor_loglik` |
| tests/test_simulator_session.py (step_n / RPC methods) | crates/voi_core/src/session.rs |
| tests/test_voi_crn.py (keys / PHYSICS_RUN_ID) | crates/voi_core/src/voi.rs |
| tests/test_rust_parity.py | skip if `_core` missing |

Not mirrored: viz, pyodide packaging, FastAPI, matplotlib, Abdella I/O.
