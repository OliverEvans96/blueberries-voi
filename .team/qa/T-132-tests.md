"""T-132 RED map — MC protection-interval quantile (CAL-B4)."""

| Criterion | Test |
|-----------|------|
| No profile → scipy closed form unchanged | `test_homogeneous_no_profile_matches_scipy` |
| Flat profile window → closed form | `test_flat_profile_matches_homogeneous_closed_form` |
| Heterogeneous window > flat μ quantile | `test_heterogeneous_window_exceeds_flat_mu` |
| `start_day` shifts quantile | `test_start_day_changes_quantile` |
| Deterministic MC | `test_mc_deterministic` |
| Rust parity golden | `test_rust_python_protection_quantile_parity` |

RED command: `uv run pytest tests/test_protection_quantile_mc.py --no-cov`
