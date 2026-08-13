# FreshRetailNet-50K — provenance

Track B ingest + derived demand product for CAL-01 calendar demand
(ADR 0115 / T-078 ingest, T-080 fit). Runtime and the slim / browser wheel
never import Hugging Face; only this offline path does.

## Source

- Dataset id: `Dingdong-Inc/FreshRetailNet-50K`
- Hub: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K
- License: **CC BY 4.0**
- Paper: arXiv:2505.16319

## Access method

Offline download / refresh via the optional `[freshnet]` extra (`datasets`) and
the ingest / fit scripts:

```bash
uv sync --extra freshnet
# deps check + print cache path (default; no multi-GB download):
uv run python scripts/fetch_freshnet.py
# download / refresh into .data/freshnet/:
uv run python scripts/fetch_freshnet.py --fetch
# fit committed demand_profile.json + fit_report.md:
uv run python scripts/fit_freshnet_demand.py
```

`datasets.load_dataset("Dingdong-Inc/FreshRetailNet-50K", cache_dir=...)` / hub
`data/train.parquet` is the access path. Do **not** add `datasets` /
huggingface-hub to core or `[browser]`.

## Local raw cache (gitignored)

- Path: `.data/freshnet/`
- Covered by the committed `.gitignore` pattern `.data/`
- Multi-GB / raw parquet dumps must **not** be committed. Derived fit output
  is committed below.

## Download date / revision

- Download date: 2026-08-13
- Hugging Face revision / commit: `08c1fab7f9257bc73679d415d65d644165d351d4`

## SKU selection rule

Categories in FreshRetailNet-50K are opaque IDs (no blueberry name match).
Selection is **rule-based** (ADR 0115):

1. Prefer fruit / high-velocity perishable `management_group` subset when IDs
   allow inspection of group labels or related columns.
2. Else pool a documented set of fresh SKUs with high sales velocity and low
   stockout-hour censoring (`stock_hour6_22_cnt` near zero preferred for mean
   estimation).
3. Commit the exact selected ID list here once exploratory stats land.

Applied for T-080 (see `fit_report.md` for full rule thresholds):

- Selected SKU IDs: 300, 117, 215, 70, 691, 191, 104, 122
- `management_group` filter: `management_group_id == 6` (largest high-velocity
  perishable pool in FRN-50K; opaque IDs — not a blueberry name match)

## Derived demand product (T-080)

- Profile: [`demand_profile.json`](./demand_profile.json) — versioned schema,
  DOW × week factors, `scale_target_mu≈30`, `demand_vm`
- Fit report: [`fit_report.md`](./fit_report.md) — SKU IDs, censoring rule,
  V/M decision, Mar–Jun seasonality honesty, ±1 scale tolerance

Fitting is **not** required for CI pytest; the committed JSON is the source of
truth. Re-fit locally with `[freshnet]` when refreshing the Hub revision.
