# T-121d QA — RED test map (Wave D: VOI CRN observation masks)

Track **T-121d** / branch `team/T-121/d-qa`. Implements Wave D acceptance from
`.team/specs/T-121.md` (D1: replace `voi.rs` `mask_obs` stub with full
`obs::mask_for` + `RichDay`).

## Coverage of acceptance criteria

- **P0 and F1 produce different scored profits on the same CRN seed when Rust
  backend runs with explicit shipments** →
  `tests/test_rust_voi_crn_masks.py::test_rust_crn_p0_profit_differs_from_f1` —
  currently failing: stub `mask_obs` treats F1 like P1; on seed 42 all masked
  filter scenarios return identical profit (`226.0`) while Python reference gives
  `P0=423.0`, `F1=429.5`.

- **F2 (lot-resolved ladder) differs structurally from P1 (aggregate totals only)**
  →
  `tests/test_rust_voi_crn_masks.py::test_rust_crn_f2_profit_differs_from_p1` —
  currently failing: stub maps F2 to the same aggregate mask as P1; Rust returns
  `P1=F2=226.0` while Python reference gives `P1=423.0`, `F2=362.5`.

## Not covered by tests

- **RichDay field population from episode day logs** — verified by Rust unit tests
  in `obs.rs` / implement D1; Python tests assert profit-level differentiation
  only.

- **``candidate_case_radius`` from ``CrnBudgets``** — no PyO3 wire yet; verify
  via Rust unit test when D1 lands.

- **Bit-identical profits vs Python** — explicitly out of scope (ADR 0127
  structural RNG parity); tests use `abs_tol=1e-6` only to reject exact collapse.

## RED proof

```bash
BLUEBERRIES_VOI_BACKEND=rust uv run pytest tests/test_rust_voi_crn_masks.py --no-cov -v
```

Both tests fail with assertion on equal profits until `voi.rs` applies full masks.
