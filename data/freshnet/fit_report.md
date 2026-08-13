# FreshNet demand profile fit report (T-080 / ADR 0115)

Generated: 2026-08-13

## Source

- Dataset: `Dingdong-Inc/FreshRetailNet-50K` (CC BY 4.0)
- Parquet: `.data/freshnet/data/train.parquet` (gitignored cache under `.data/freshnet/`)
- Hugging Face revision: `08c1fab7f9257bc73679d415d65d644165d351d4`
- Fit uses the full train split parquet (no row subsample).

## Selected SKU IDs

Selected SKU IDs: 300, 117, 215, 70, 691, 191, 104, 122

Selection rule (reproducible):

1. Restrict to `management_group_id == 6` (largest high-velocity
   perishable pool in FRN-50K; category labels are opaque - not a blueberry
   name match).
2. Require >= 10000 store-day rows, mean `sale_amount` >= 1.0,
   and >= 45% days with `stock_hour6_22_cnt == 0`.
3. Rank by total `sale_amount` and take the top 8 product IDs.

## Censoring

Censoring rule: keep only store-days with `stock_hour6_22_cnt <= 0`
(prefer low/zero stockout hours for mean estimation). Full two-stage latent
demand recovery is out of scope for CAL-01 (ADR 0115).

Fit rows after filter: **143681** across
**90** unique dates.

## Scale (operational mu~30)

Relative DOW x week factors are mean-normalized so that

`mu(day) = scale_target_mu * dow_factors[dow] * week_factors[week]`

with `scale_target_mu = 30.0` (MOD-26 continuity).

**Tolerance:** absolute **+/- 1** on `scale_target_mu` vs 30
(tests lock absolute tol = 1, i.e. within 1 of 30).

Operational mean check over observed Mar-Jun dates:
`scale_target_mu * mean(dow*week) ~ 30.0000`
(within 1 of 30).

Chinese `sale_amount` is globally normalized - **not** transferred as punnets
or yuan into `ProfitCosts`.

## V/M choice

- Empirical median within-cell V/M ~ 1.077
- Pooled (calendar-ignored) V/M ~ 1.251
- **Decision:** keep 2.0 (MOD-26 continuity); empirical median within-cell V/M~1.077, pooled V/M~1.251 - refit near 1.0 rejected as under-dispersed for VOI base case
- Profile field `demand_vm` = **2.0**

## Mar-Jun seasonality honesty

FreshRetailNet-50K covers roughly **March-June 2024** only
(window `2024-03-28` .. `2024-06-25`).
"Seasonal" here means DOW + week-index factors over that **Mar-Jun** window -
**not** full annual seasonality. Week index 0 starts at
`2024-03-28` (13 weeks).

## Schema

Committed artifact: `data/freshnet/demand_profile.json`

- `schema_version`: 1
- `dow_factors`: length-7 multipliers (Monday=0)
- `week_factors`: length-13 multipliers
- `scale_target_mu`, `demand_vm`

Re-run: `uv sync --extra freshnet && uv run python scripts/fit_freshnet_demand.py`
