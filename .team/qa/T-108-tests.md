# T-108 implement: remaining kernel + FFI tests

| Python | Rust |
| --- | --- |
| test_age_likelihood / arrival_only (LL + weights) | exact_ll.rs, rbpf.rs filter_step |
| test_rollout.py (candidates, salvage empty, H<=0, case multiple) | rollout.rs |
| test_closed_loop_episode.py (n_burn, scored slice) | episode.rs |
| test_voi_crn.py | voi.rs |

`cargo test -p voi_core` is the gate. PyO3 via `maturin develop --manifest-path crates/voi_py/Cargo.toml`.
