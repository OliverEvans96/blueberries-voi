# T-141 qa-likelihood-guards — RED proof

Shard: qa-likelihood-guards  
Parent: team/T-141/architect

## AC → test map

| Criterion | Test |
|-----------|------|
| AC-L1 (delete interval primitives) | `superseded_interval_spoil_primitives_are_gone` |
| AC-L2 (PB DP) | `t141_poisson_binomial` integration tests |
| AC-L5 (guards + Python contracts) | `unit_pf_ac` wiring, `tests/test_unit_pf.py` |

## RED command

```bash
cargo test -p voi_core t141_poisson_binomial superseded_interval -- --nocapture
uv run pytest tests/test_unit_pf.py -k "pb or spoil or superseded_interval" --no-cov -x
```

## RED result

- Compile error: `pb_log_pmf`, `pb_loglik_by_lot`, etc. not in `unit_ll`.
- `superseded_interval_spoil_primitives_are_gone`: **FAIL** — interval symbols still present in production.
- Python router tests: **FAIL** — `unit_pf.rs` still uses `delta_interval_loglik`.

Status: **RED**
