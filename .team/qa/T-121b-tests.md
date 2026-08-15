# T-121b — RED test map (Wave B policy engine)

Track: policy dispatch on belief counts (`B1`–`B4`). Proved with:

```bash
uv run pytest tests/test_rust_act_policies.py --no-cov -v
```

## Coverage of acceptance criteria

- **B4:** Python `EngineSession.act(policy=..., **budgets)` routes constant kwargs → `tests/test_rust_act_policies.py::test_rust_pyo3_act_accepts_constant_order_qty_kwarg` — currently failing: `PyEngineSession.act` lacks `order_qty` / `q` parameters
- **B2/B4:** `constant_order` case-multiples via rust `act` → `tests/test_rust_act_policies.py::test_constant_policy_returns_case_multiple_on_order_day` — currently failing: blocked on missing constant budget kwargs (same root cause as B4)
- **B3:** `damped_sw` case-multiples from belief → `tests/test_rust_act_policies.py::test_damped_sw_policy_returns_case_multiple` — passes today (case multiple only); belief parity enforced in `test_damped_sw_matches_python_belief_reference`
- **B3:** `rollout` case-multiples from belief → `tests/test_rust_act_policies.py::test_rollout_policy_returns_case_multiple` — passes today (case multiple only); belief parity enforced in `test_rollout_matches_python_belief_reference`
- **B3:** damped_sw uses belief not truth → `tests/test_rust_act_policies.py::test_damped_sw_matches_python_belief_reference` — currently failing: rust=88 vs python belief reference=56 (truth-state `act_rollout`)
- **B3:** rollout uses belief not truth → `tests/test_rust_act_policies.py::test_rollout_matches_python_belief_reference` — currently failing: rust=88 vs python belief reference=64
- **B3:** rollout ≠ constant under filter + nontrivial belief → `tests/test_rust_act_policies.py::test_rollout_differs_from_constant_when_filter_enabled` — currently failing: rollout truth-parity half passes (`88 != 16`) but belief reference assert fails (`88 != 64`)
- **B3:** separate damped_sw vs rollout dispatch → `tests/test_rust_act_policies.py::test_damped_sw_and_rollout_are_distinct_when_reference_differs` — currently failing: both policies return 88 via shared `act_rollout`

## Not covered by tests

- **B1:** `mean_bank` export and empty-belief fallback — Rust unit tests in `belief_flat.rs` (implementer); no Python surface yet
- **B2:** `constant_order(q, case_size)` Rust unit pairs and vs damped_sw — Rust unit tests in `policy.rs` (implementer)
- **B3:** Filter-enabled Rust unit: true counts ≠ belief mean changes rollout order — see optional spec below; implement in `session.rs` `#[cfg(test)]`
- **B3:** Budget override `alpha` changes damped_sw — Rust unit test (implementer)
- **B3:** `act_rollout()` alias — covered indirectly once B3/B4 land; no dedicated Python test (RPC/PyO3 alias smoke in implement)
- **B4:** WASM `handle_rpc` `"act"` policy+budget params — T-121a/b implement track; verify in Wave E integration

## Optional Rust unit test spec (implementer — truth ≠ belief)

Add to `crates/voi_core/src/session.rs` tests (B3 AC):

1. Configure `EngineSession` with `enable_filter=true`, non-trivial shipments, fixed seed.
2. Advance several days with zero orders so filter updates belief while shelf truth diverges from particle mean (mirror truth-vs-belief audit fixture seed `99`, warm 6 days).
3. Capture `self.state.counts` (truth) and `mean_bank(&particle_bank)` counts.
4. Assert `truth_counts != belief_mean_counts` element-wise (or L1 norm > threshold).
5. Assert `act(policy="rollout")` order quantity ≠ hypothetical order computed if `damped_sw_order` / `rollout_order` were called with **truth** counts instead of belief mean.
6. Assert `act(policy="rollout")` order **equals** order from belief mean (same seed, same budgets).

This complements Python structural parity tests; tolerances on order qty only (not belief arrays), per ADR 0127 / plan risk notes.
