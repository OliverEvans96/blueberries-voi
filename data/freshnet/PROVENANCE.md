# FreshRetailNet-50K — provenance

Track B ingest for CAL-01 calendar demand (ADR 0112 / T-078). Runtime and the
slim / browser wheel never import Hugging Face; only this offline path does.

## Source

- Dataset id: `Dingdong-Inc/FreshRetailNet-50K`
- Hub: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K
- License: **CC BY 4.0**
- Paper: arXiv:2505.16319

## Access method

Offline download / refresh via the optional `[freshnet]` extra (`datasets`) and
the ingest script:

```bash
uv sync --extra freshnet
# deps check + print cache path (default; no multi-GB download):
uv run python scripts/fetch_freshnet.py
# download / refresh into .data/freshnet/:
uv run python scripts/fetch_freshnet.py --fetch
```

`datasets.load_dataset("Dingdong-Inc/FreshRetailNet-50K", cache_dir=...)` is the
access path. Do **not** add `datasets` / huggingface-hub to core or `[browser]`.

## Local raw cache (gitignored)

- Path: `.data/freshnet/`
- Covered by the committed `.gitignore` pattern `.data/`
- Multi-GB parquet dumps must **not** be committed. Derived fit output
  (`demand_profile.json`) is a separate ticket (T-080).

## Download date / revision

- Download date: _TBD — fill when first fetch is run_
- Hugging Face revision / commit: _TBD — record after `scripts/fetch_freshnet.py`_

## SKU selection rule

Categories in FreshRetailNet-50K are opaque IDs (no blueberry name match).
Selection is **rule-based** (ADR 0112):

1. Prefer fruit / high-velocity perishable `management_group` subset when IDs
   allow inspection of group labels or related columns.
2. Else pool a documented set of fresh SKUs with high sales velocity and low
   stockout-hour censoring (`stock_hour6_22_cnt` near zero preferred for mean
   estimation).
3. Commit the exact selected ID list here once exploratory stats land (T-080
   may fill IDs). Until then:

- Selected SKU IDs: _TBD (placeholder — rule text above is binding)_
- `management_group` filter: _TBD_

## Scale / fit (out of scope for T-078)

Fitting `demand_profile.json` (relative DOW × week shape, scale to operational
μ≈30, censoring) is **T-080**. This ticket only ships ingest + provenance.
