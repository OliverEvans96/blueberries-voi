# T-141 qa-filter — RED proof

Shard: qa-filter  
Parent: team/T-141/architect

## AC → test map

| Criterion | Test |
|-----------|------|
| AC-T2 (independent δ_i in truth) | `t141_independent_aging_two_units_can_split_spoil` |
| AC-G3 (count_bias == 0) | `gsin_upc_count_bias_is_zero_on_spoilage_rungs` |
| AC-G4 (GSIN ≤ UPC) | `gsin_upc_gsin_le_upc_on_comparable_metrics` |

## RED command

```bash
cargo test -p voi_core t141_independent_aging gsin_upc_ac12 -- --nocapture
```

## RED result

- `t141_independent_aging_two_units_can_split_spoil`: **FAIL** — shared decrement ages both units identically; split spoil never observed.
- `gsin_upc_count_bias_is_zero_on_spoilage_rungs`: **FAIL** until PB filter + independent aging land.

Status: **RED**
