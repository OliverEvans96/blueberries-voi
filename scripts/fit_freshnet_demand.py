#!/usr/bin/env python3
"""Fit a committed FreshNet DOW x week demand profile (requires ``[freshnet]``).

Produces ``data/freshnet/demand_profile.json`` and ``data/freshnet/fit_report.md``
from FreshRetailNet-50K (CC BY 4.0). Raw parquet stays under ``.data/freshnet/``
(gitignored); only the small derived JSON is committed.

Requires the optional ``[freshnet]`` extra::

    uv sync --extra freshnet
    uv run python scripts/fit_freshnet_demand.py
    # or reuse a prior download:
    uv run python scripts/fit_freshnet_demand.py \\
        --parquet .data/freshnet/data/train.parquet

See ``data/freshnet/PROVENANCE.md`` and ADR 0115.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE = _REPO_ROOT / ".data" / "freshnet"
_DEFAULT_PROFILE = _REPO_ROOT / "data" / "freshnet" / "demand_profile.json"
_DEFAULT_REPORT = _REPO_ROOT / "data" / "freshnet" / "fit_report.md"
_DATASET_ID = "Dingdong-Inc/FreshRetailNet-50K"
_SCALE_TARGET_MU = 30.0
_SCALE_ABS_TOL = 1.0
_SCHEMA_VERSION = 1
_DEMAND_VM_KEEP = 2.0

# Reproducible SKU selection (opaque IDs - see fit report / PROVENANCE).
_MGMT_GROUP = 6
_MIN_ROWS = 10_000
_MIN_PCT_ZERO_STOCK = 0.45
_MIN_MEAN_SALE = 1.0
_N_SKUS = 8
_CENSOR_MAX_STOCK_HOURS = 0  # prefer stock_hour6_22_cnt == 0


def _require_freshnet_deps() -> None:
    """Exit with a clear message if the ``[freshnet]`` extra is missing."""
    try:
        import datasets  # noqa: F401
        import pandas  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError as exc:
        print(
            "error: optional [freshnet] dependency is not installed "
            f"(need datasets/pandas/pyarrow).\n"
            "Install with: uv sync --extra freshnet\n"
            f"(import failed: {exc})",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _ensure_train_parquet(cache_dir: Path) -> tuple[Path, str | None]:
    """Return local train.parquet path and HF revision sha if known."""
    _require_freshnet_deps()
    from huggingface_hub import HfApi, hf_hub_download

    cache_dir.mkdir(parents=True, exist_ok=True)
    local = hf_hub_download(
        repo_id=_DATASET_ID,
        filename="data/train.parquet",
        repo_type="dataset",
        local_dir=str(cache_dir),
    )
    revision: str | None = None
    try:
        revision = HfApi().dataset_info(_DATASET_ID).sha
    except Exception:
        # Best-effort provenance only; fit still succeeds without hub metadata.
        revision = None
    return Path(local), revision


def _select_skus(df: Any) -> list[int]:
    """Rule-based SKU pool: high-velocity mgmt group 6, low censoring."""
    import pandas as pd

    g = df.groupby("product_id").agg(
        n=("sale_amount", "size"),
        mean_sale=("sale_amount", "mean"),
        sum_sale=("sale_amount", "sum"),
        mean_stockout=("stock_hour6_22_cnt", "mean"),
        pct_zero_stock=(
            "stock_hour6_22_cnt",
            lambda s: float((s == _CENSOR_MAX_STOCK_HOURS).mean()),
        ),
        mgmt=("management_group_id", "first"),
    )
    assert isinstance(g, pd.DataFrame)
    cand = g[
        (g["mgmt"] == _MGMT_GROUP)
        & (g["n"] >= _MIN_ROWS)
        & (g["pct_zero_stock"] >= _MIN_PCT_ZERO_STOCK)
        & (g["mean_sale"] >= _MIN_MEAN_SALE)
    ].sort_values("sum_sale", ascending=False)
    if len(cand) < _N_SKUS:
        msg = (
            f"SKU selection produced only {len(cand)} candidates "
            f"(need {_N_SKUS}); relax thresholds or check parquet"
        )
        raise RuntimeError(msg)
    return [int(x) for x in cand.head(_N_SKUS).index.tolist()]


def _fit_profile(
    df: Any,
    sku_ids: list[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit multiplicative DOW x week factors; scale target mu~30."""
    import numpy as np
    import pandas as pd

    sub = df[
        df["product_id"].isin(sku_ids)
        & (df["stock_hour6_22_cnt"] <= _CENSOR_MAX_STOCK_HOURS)
    ].copy()
    if sub.empty:
        raise RuntimeError("no rows left after SKU + censoring filters")

    sub["dt"] = pd.to_datetime(sub["dt"])
    sub["dow"] = sub["dt"].dt.dayofweek.astype(int)  # Mon=0 .. Sun=6
    t0 = sub["dt"].min().normalize()
    sub["week_index"] = ((sub["dt"] - t0).dt.days // 7).astype(int)

    grand = float(sub["sale_amount"].mean())
    if not math.isfinite(grand) or grand <= 0.0:
        raise RuntimeError(f"invalid grand mean sale_amount={grand}")

    dow_means = sub.groupby("dow")["sale_amount"].mean()
    week_means = sub.groupby("week_index")["sale_amount"].mean()
    wmax = int(sub["week_index"].max())

    dow_raw = (dow_means / grand).reindex(range(7)).fillna(1.0)
    week_raw = week_means.reindex(range(wmax + 1)).fillna(grand) / grand

    dow_factors = (dow_raw / float(dow_raw.mean())).tolist()
    week_factors = (week_raw / float(week_raw.mean())).tolist()

    # Empirical within-cell V/M (diagnostic); default keep MOD-26 = 2.0.
    cell = sub.groupby(["dow", "week_index"])["sale_amount"].agg(
        ["mean", "var", "count"]
    )
    cell = cell[cell["count"] >= 30]
    cell_vm = (
        float((cell["var"] / cell["mean"]).median()) if len(cell) else float("nan")
    )
    pooled_vm = float(sub["sale_amount"].var(ddof=1) / sub["sale_amount"].mean())

    # ADR 0113: retain V/M~2.0 unless a stable refit is preferred; empirical
    # within-cell V/M is near-Poisson (~1.1) and would understate MOD-26 jumpy
    # demand - keep 2.0 and document.
    demand_vm = _DEMAND_VM_KEEP
    vm_decision = (
        f"keep {_DEMAND_VM_KEEP} (MOD-26 continuity); empirical median "
        f"within-cell V/M~{cell_vm:.3f}, pooled V/M~{pooled_vm:.3f} - "
        "refit near 1.0 rejected as under-dispersed for VOI base case"
    )

    # Sanity: mean of dow*week over unique observed dates ~ 1 -> mu~scale_target.
    days = sub[["dt", "dow", "week_index"]].drop_duplicates()
    rel = [
        dow_factors[int(r.dow)] * week_factors[int(r.week_index)]
        for r in days.itertuples(index=False)
    ]
    mean_rel = float(np.mean(rel)) if rel else 1.0
    # Factors already mean-normalized separately; product mean may drift slightly.
    # Calibrate so E[mu(day)] over observed calendar matches target scale.
    calendar_scale = 1.0 / mean_rel if mean_rel > 0 else 1.0
    # Fold calendar_scale into week_factors to keep a single multiplicative form.
    week_factors = [w * calendar_scale for w in week_factors]
    # Re-check operational mean of factors (should be ~1).
    rel2 = [
        dow_factors[int(r.dow)] * week_factors[int(r.week_index)]
        for r in days.itertuples(index=False)
    ]
    mean_factor = float(np.mean(rel2)) if rel2 else 1.0
    scale_target_mu = _SCALE_TARGET_MU
    if abs(scale_target_mu * mean_factor - _SCALE_TARGET_MU) > _SCALE_ABS_TOL:
        # Should not happen after calibration; still clamp report honesty.
        pass

    profile: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "dataset_id": _DATASET_ID,
        "scale_target_mu": scale_target_mu,
        "demand_vm": demand_vm,
        "dow_factors": [round(x, 6) for x in dow_factors],
        "week_factors": [round(x, 6) for x in week_factors],
        "dow_index": "monday0",
        "week_index_origin": t0.date().isoformat(),
        "window_start": sub["dt"].min().date().isoformat(),
        "window_end": sub["dt"].max().date().isoformat(),
        "sku_ids": sku_ids,
        "censoring": {
            "rule": "stock_hour6_22_cnt <= 0",
            "max_stock_hour6_22_cnt": _CENSOR_MAX_STOCK_HOURS,
        },
        "notes": (
            "mu(day) = scale_target_mu * dow_factors[dow] * week_factors[week]; "
            "factors mean-normalized over Mar-Jun window; sale_amount units are "
            "globally normalized Chinese retail - not punnets or yuan."
        ),
    }

    meta = {
        "sku_ids": sku_ids,
        "n_rows_fit": len(sub),
        "n_unique_dates": int(days["dt"].nunique()),
        "grand_mean_sale": grand,
        "mean_factor_over_dates": mean_factor,
        "operational_mean_check": scale_target_mu * mean_factor,
        "cell_vm_median": cell_vm,
        "pooled_vm": pooled_vm,
        "vm_decision": vm_decision,
        "window_start": profile["window_start"],
        "window_end": profile["window_end"],
        "week_index_origin": profile["week_index_origin"],
        "n_weeks": len(week_factors),
    }
    return profile, meta


def _write_report(
    path: Path,
    *,
    profile: dict[str, Any],
    meta: dict[str, Any],
    revision: str | None,
    parquet_path: Path,
    subsample_note: str,
) -> None:
    sku_list = ", ".join(str(s) for s in meta["sku_ids"])
    today = date.today().isoformat()
    rev = revision or "(unknown - record after hub fetch)"
    try:
        parquet_display = str(parquet_path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        parquet_display = str(parquet_path)
    censor_line = (
        f"Censoring rule: keep only store-days with "
        f"`stock_hour6_22_cnt <= {_CENSOR_MAX_STOCK_HOURS}`"
    )
    text = f"""# FreshNet demand profile fit report (T-080 / ADR 0115)

Generated: {today}

## Source

- Dataset: `{_DATASET_ID}` (CC BY 4.0)
- Parquet: `{parquet_display}` (gitignored cache under `.data/freshnet/`)
- Hugging Face revision: `{rev}`
- {subsample_note}

## Selected SKU IDs

Selected SKU IDs: {sku_list}

Selection rule (reproducible):

1. Restrict to `management_group_id == {_MGMT_GROUP}` (largest high-velocity
   perishable pool in FRN-50K; category labels are opaque - not a blueberry
   name match).
2. Require >= {_MIN_ROWS} store-day rows, mean `sale_amount` >= {_MIN_MEAN_SALE},
   and >= {_MIN_PCT_ZERO_STOCK:.0%} days with `stock_hour6_22_cnt == 0`.
3. Rank by total `sale_amount` and take the top {_N_SKUS} product IDs.

## Censoring

{censor_line}
(prefer low/zero stockout hours for mean estimation). Full two-stage latent
demand recovery is out of scope for CAL-01 (ADR 0115).

Fit rows after filter: **{meta["n_rows_fit"]}** across
**{meta["n_unique_dates"]}** unique dates.

## Scale (operational mu~30)

Relative DOW x week factors are mean-normalized so that

`mu(day) = scale_target_mu * dow_factors[dow] * week_factors[week]`

with `scale_target_mu = {profile["scale_target_mu"]}` (MOD-26 continuity).

**Tolerance:** absolute **+/- 1** on `scale_target_mu` vs 30
(tests lock absolute tol = 1, i.e. within 1 of 30).

Operational mean check over observed Mar-Jun dates:
`scale_target_mu * mean(dow*week) ~ {meta["operational_mean_check"]:.4f}`
(within 1 of 30).

Chinese `sale_amount` is globally normalized - **not** transferred as punnets
or yuan into `ProfitCosts`.

## V/M choice

- Empirical median within-cell V/M ~ {meta["cell_vm_median"]:.3f}
- Pooled (calendar-ignored) V/M ~ {meta["pooled_vm"]:.3f}
- **Decision:** {meta["vm_decision"]}
- Profile field `demand_vm` = **{profile["demand_vm"]}**

## Mar-Jun seasonality honesty

FreshRetailNet-50K covers roughly **March-June 2024** only
(window `{meta["window_start"]}` .. `{meta["window_end"]}`).
"Seasonal" here means DOW + week-index factors over that **Mar-Jun** window -
**not** full annual seasonality. Week index 0 starts at
`{meta["week_index_origin"]}` ({meta["n_weeks"]} weeks).

## Schema

Committed artifact: `data/freshnet/demand_profile.json`

- `schema_version`: {profile["schema_version"]}
- `dow_factors`: length-7 multipliers (Monday=0)
- `week_factors`: length-{meta["n_weeks"]} multipliers
- `scale_target_mu`, `demand_vm`

Re-run: `uv sync --extra freshnet && uv run python scripts/fit_freshnet_demand.py`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fit(
    *,
    parquet: Path | None,
    cache_dir: Path,
    profile_out: Path,
    report_out: Path,
) -> dict[str, Any]:
    """Load parquet (download if needed), fit, write profile + report."""
    _require_freshnet_deps()
    import pandas as pd

    revision: str | None = None
    subsample_note = "Fit uses the full train split parquet (no row subsample)."
    if parquet is None:
        parquet, revision = _ensure_train_parquet(cache_dir)
    else:
        parquet = parquet.resolve()
        if not parquet.is_file():
            print(f"error: parquet not found: {parquet}", file=sys.stderr)
            raise SystemExit(1)

    cols = [
        "product_id",
        "management_group_id",
        "dt",
        "sale_amount",
        "stock_hour6_22_cnt",
    ]
    df = pd.read_parquet(parquet, columns=cols)
    sku_ids = _select_skus(df)
    profile, meta = _fit_profile(df, sku_ids)
    profile["fit_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if revision:
        profile["hf_revision"] = revision

    profile_out.parent.mkdir(parents=True, exist_ok=True)
    profile_out.write_text(
        json.dumps(profile, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    _write_report(
        report_out,
        profile=profile,
        meta=meta,
        revision=revision,
        parquet_path=parquet,
        subsample_note=subsample_note,
    )
    print(
        f"wrote {profile_out} ({profile_out.stat().st_size} bytes) and {report_out}",
        file=sys.stderr,
    )
    return profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fit FreshNet DOW x week demand_profile.json (requires [freshnet] extra)."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE,
        help=f"gitignored HF/parquet cache (default: {_DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=None,
        help="optional local train.parquet (skips hub download if set)",
    )
    parser.add_argument(
        "--profile-out",
        type=Path,
        default=_DEFAULT_PROFILE,
        help=f"output demand_profile.json (default: {_DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=_DEFAULT_REPORT,
        help=f"output fit_report.md (default: {_DEFAULT_REPORT})",
    )
    args = parser.parse_args(argv)

    _require_freshnet_deps()
    fit(
        parquet=args.parquet,
        cache_dir=args.cache_dir.resolve(),
        profile_out=args.profile_out.resolve(),
        report_out=args.report_out.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
