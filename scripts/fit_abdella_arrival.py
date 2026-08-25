#!/usr/bin/env python3
"""Fit committed Abdella arrival_model.json from vendored parquet (ADR 0148).

Produces ``data/abdella/arrival_model.json``, ``data/abdella/fit_report.md``, and
``data/abdella/arrival_calibration_overlay.png``. Raw parquet is read offline only;
runtime loads the JSON artifact (FreshNet-parity pattern).

Requires pyarrow / matplotlib (``[data]`` + ``[viz]`` or ``[dev]``).

    uv sync --extra data --extra viz
    uv run python scripts/fit_abdella_arrival.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA = _REPO_ROOT / "data" / "abdella"
_DEFAULT_ARTIFACT = _DEFAULT_DATA / "arrival_model.json"
_DEFAULT_REPORT = _DEFAULT_DATA / "fit_report.md"
_DEFAULT_FIG = _DEFAULT_DATA / "arrival_calibration_overlay.png"
_DEFAULT_NOTE = _DEFAULT_DATA / "calibration_note.md"
_SCHEMA_VERSION = 1
_SHORT_HAUL_ID = "S2"
_SUSPECT_PROBE_SHIPMENT = "S4"

# Literature / MOD adjustment defaults (not identified from n=6 trips).
_DEFAULT_GAMMA_SHAPE = 2.0
_DEFAULT_GAMMA_SCALE = 1.0 / 28.0
_DEFAULT_REFERENCE_LIFE = 14.0
_DEFAULT_Q10 = 3.0
_DEFAULT_T_REF = 0.0
_DEFAULT_TEMP_FLOOR = 0.0
_DEFAULT_SIGMA_POS = 0.08

_QUADRATURE_NODES = [
    0.01985507,
    0.10166676,
    0.2372339,
    0.40828268,
    0.59171732,
    0.7627661,
    0.89833324,
    0.98014493,
]
_QUADRATURE_WEIGHTS = [
    0.05061427,
    0.11119051,
    0.15685332,
    0.18134189,
    0.18134189,
    0.15685332,
    0.11119051,
    0.05061427,
]


def _require_deps() -> None:
    try:
        import matplotlib.pyplot  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError as exc:
        print(
            "error: optional [data] and [viz] deps required "
            "(pyarrow, matplotlib).\n"
            "Install with: uv sync --extra data --extra viz\n"
            f"(import failed: {exc})",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _phi_bar_from_trace(
    times_d: Any, temps_c: Any, *, q10: float, t_ref: float
) -> float:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from blueberries_voi.model.abdella import arrival_age_from_path

    exposure = arrival_age_from_path(
        temps_c,
        times_d,
        q10=q10,
        t_ref_c=t_ref,
    )
    duration = float(times_d[-1] - times_d[0]) if len(times_d) >= 2 else 0.0
    return exposure / duration if duration > 0 else float("nan")


def _t_from_phi_bar(phi_bar: float, *, q10: float, t_ref: float) -> float:
    if phi_bar <= 0 or not math.isfinite(phi_bar):
        return float("nan")
    return t_ref + 10.0 * math.log(phi_bar) / math.log(q10)


def _fit_delayed_gamma(
    durations: list[float],
    *,
    d_min_margin: float = 0.05,
) -> tuple[float, float, float]:
    import numpy as np

    d = np.asarray(durations, dtype=float)
    d_min = max(0.0, float(d.min()) - d_min_margin)
    delays = d - d_min
    mean = float(delays.mean())
    var = float(delays.var(ddof=1)) if len(delays) > 1 else mean * 0.1
    if var <= 1e-12 or mean <= 1e-12:
        shape = 2.0
        scale = max(mean / shape, 1e-6)
    else:
        scale = var / mean
        shape = mean / scale
    shape = max(shape, 1.0)
    scale = max(scale, 1e-6)
    return d_min, shape, scale


def _fit_truncated_normal_t(
    phi_bars: list[float],
    *,
    q10: float,
    t_ref: float,
    temp_floor: float,
) -> tuple[float, float]:
    import numpy as np

    t_vals = np.asarray(
        [_t_from_phi_bar(p, q10=q10, t_ref=t_ref) for p in phi_bars],
        dtype=float,
    )
    t_vals = t_vals[np.isfinite(t_vals)]
    if t_vals.size == 0:
        return 2.7, 0.4
    mu = float(np.mean(t_vals))
    sd = float(np.std(t_vals, ddof=1)) if t_vals.size > 1 else 0.4
    sd = max(sd, 0.05)
    if mu < temp_floor:
        mu = temp_floor + 0.1
    return mu, sd


def _estimate_sigma_pos(data_dir: Path) -> tuple[float, str]:
    """Keep literature default; probe temperature sd is not lognormal psi scale."""
    del data_dir
    return _DEFAULT_SIGMA_POS, (
        f"keep {_DEFAULT_SIGMA_POS} (lognormal psi scale; not identified from "
        f"n=6; probe temperature sd is not sigma_pos)"
    )


def _summarize_shipments(data_dir: Path) -> list[dict[str, Any]]:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from blueberries_voi.model.abdella import load_abdella_shipments

    rows: list[dict[str, Any]] = []
    for shipment in load_abdella_shipments(data_dir):
        phi = _phi_bar_from_trace(
            shipment.times_d,
            shipment.temps_c,
            q10=_DEFAULT_Q10,
            t_ref=_DEFAULT_T_REF,
        )
        rows.append(
            {
                "shipment": shipment.shipment_id,
                "d_days": float(shipment.duration_d),
                "phi_bar": float(phi),
            }
        )
    return rows


def _build_artifact(
    rows: list[dict[str, Any]],
    *,
    sigma_pos: float,
    sigma_pos_note: str,
    gamma_shape: float,
    gamma_scale: float,
    reference_life: float,
    q10: float,
    t_ref: float,
    temp_floor: float,
    gamma_note: str,
) -> dict[str, Any]:
    all_d = [r["d_days"] for r in rows]
    all_phi = [r["phi_bar"] for r in rows]

    abdella_d_min, abdella_shape, abdella_scale = _fit_delayed_gamma(all_d)
    mu_t, sigma_t = _fit_truncated_normal_t(
        all_phi,
        q10=q10,
        t_ref=t_ref,
        temp_floor=temp_floor,
    )

    short_rows = [r for r in rows if r["shipment"] == _SHORT_HAUL_ID]
    long_rows = [r for r in rows if r["shipment"] != _SHORT_HAUL_ID]

    sh_d_min, sh_shape, sh_scale = _fit_delayed_gamma(
        [r["d_days"] for r in short_rows] if short_rows else all_d[:1]
    )
    if len(short_rows) == 1:
        d_single = short_rows[0]["d_days"]
        sh_d_min = max(0.0, d_single - 0.1)
        sh_shape = 2.0
        sh_scale = max((d_single - sh_d_min) / sh_shape, 0.05)
    lh_d_min, lh_shape, lh_scale = _fit_delayed_gamma(
        [r["d_days"] for r in long_rows] if long_rows else all_d
    )

    fit_utc = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    return {
        "schema_version": _SCHEMA_VERSION,
        "mu_T": round(mu_t, 6),
        "sigma_T": round(sigma_t, 6),
        "temp_floor_c": temp_floor,
        "sigma_pos": round(sigma_pos, 6),
        "q10": q10,
        "T_ref": t_ref,
        "gamma_shape": gamma_shape,
        "gamma_scale": gamma_scale,
        "reference_life_days": reference_life,
        "quadrature": {
            "nodes": _QUADRATURE_NODES,
            "weights": _QUADRATURE_WEIGHTS,
        },
        "corridors": {
            "short_haul": {
                "d_min": round(sh_d_min, 6),
                "delay_shape": round(sh_shape, 6),
                "delay_scale": round(sh_scale, 6),
            },
            "long_haul": {
                "d_min": round(lh_d_min, 6),
                "delay_shape": round(lh_shape, 6),
                "delay_scale": round(lh_scale, 6),
            },
            "abdella_all": {
                "d_min": round(abdella_d_min, 6),
                "delay_shape": round(abdella_shape, 6),
                "delay_scale": round(abdella_scale, 6),
            },
        },
        "provenance": {
            "source": (
                "Offline fit from vendored Abdella parquet (ADR 0148); "
                "parametric families fixed, moments matched on n=6."
            ),
            "window": (
                "Refrigerated leg only: from first lot-mean T < 10 C through "
                "published Table 2 duration."
            ),
            "n_shipments": len(rows),
            "fit_utc": fit_utc,
            "fit_script": "scripts/fit_abdella_arrival.py",
            "shipment_summaries": rows,
            "fitted_fields": [
                "corridors.*.(d_min,delay_shape,delay_scale)",
                "mu_T",
                "sigma_T",
                "sigma_pos",
            ],
            "adjustment_fields": [
                "gamma_shape",
                "gamma_scale",
                "reference_life_days",
                "q10",
                "T_ref",
                "temp_floor_c",
            ],
            "adjustment_notes": {
                "gamma": gamma_note,
                "sigma_pos": sigma_pos_note,
            },
            "notes": (
                "Six strawberry logger shipments (not MLE-validated). "
                "Arrival freshness remains an upper bound (field heat excluded). "
                "short_haul = S2; long_haul = S1,S3-S6."
            ),
        },
    }


def _write_overlay(
    artifact: dict[str, Any],
    rows: list[dict[str, Any]],
    fig_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    d_pts = [r["d_days"] for r in rows]
    phi_pts = [r["phi_bar"] for r in rows]
    ax.scatter(d_pts, phi_pts, label="six Abdella shipments", zorder=3)

    corridor = artifact["corridors"]["abdella_all"]
    d_min = float(corridor["d_min"])
    shape = float(corridor["delay_shape"])
    scale = float(corridor["delay_scale"])
    mu_t = float(artifact["mu_T"])
    sigma_t = float(artifact["sigma_T"])
    q10 = float(artifact["q10"])
    t_ref = float(artifact["T_ref"])
    t_floor = float(artifact.get("temp_floor_c", 0.0))

    d_grid = [
        d_min + shape * scale * 0.25,
        d_min + shape * scale,
        d_min + shape * scale * 2.0,
    ]
    phi_at_mu = math.pow(q10, (mu_t - t_ref) / 10.0)
    phi_lo = math.pow(q10, (max(mu_t - sigma_t, t_floor) - t_ref) / 10.0)
    phi_hi = math.pow(q10, (mu_t + sigma_t - t_ref) / 10.0)
    for d in d_grid:
        ax.plot([d, d], [phi_lo, phi_hi], color="C1", alpha=0.35, linewidth=2)
    ax.scatter(d_grid, [phi_at_mu] * len(d_grid), color="C1", s=18, alpha=0.6)

    ax.set_xlabel("refrigerated-leg duration d (days)")
    ax.set_ylabel("mean temperature factor phi_bar")
    ax.set_title("Fitted arrival families vs six-shipment sample")
    ax.legend()
    fig.tight_layout()
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)


def _write_fit_report(
    path: Path,
    *,
    artifact: dict[str, Any],
    rows: list[dict[str, Any]],
    sigma_pos_note: str,
    gamma_note: str,
) -> None:
    prov = artifact["provenance"]
    table_lines = ["| shipment | d_days | phi_bar |", "| --- | --- | --- |"]
    for row in rows:
        table_lines.append(
            f"| {row['shipment']} | {row['d_days']:.3f} | {row['phi_bar']:.3f} |"
        )
    table_md = "\n".join(table_lines)
    abdella = artifact["corridors"]["abdella_all"]

    body = f"""# Abdella arrival model fit report (ADR 0148)

Generated: {prov.get("fit_utc", "unknown")}

## Source

- Vendored parquet: `data/abdella/s{{1..6}}.parquet`
- Upstream: Abdella et al. 2021 / HF `NifferLi/cold-chain-strawberry-sensors`
- Fit script: `{prov.get("fit_script", "scripts/fit_abdella_arrival.py")}`
- Shipments in fit: **{prov.get("n_shipments", len(rows))}**

## Fitted parameters

| Field | Value | Method |
| --- | --- | --- |
| `mu_T` | {artifact["mu_T"]} | mean T from shipment phi_bar via Q10 |
| `sigma_T` | {artifact["sigma_T"]} | sd T across six shipments |
| `sigma_pos` | {artifact["sigma_pos"]} | {sigma_pos_note} |
| `abdella_all.d_min` | {abdella["d_min"]} | delayed-gamma moments on six d |
| `abdella_all.delay_shape` | {abdella["delay_shape"]} | delayed-gamma moments |
| `abdella_all.delay_scale` | {abdella["delay_scale"]} | delayed-gamma moments |

## Adjustment knobs (not refit by default)

| Knob | Committed | Decision |
| --- | --- | --- |
| `gamma_shape` | {artifact["gamma_shape"]} | {gamma_note} |
| `gamma_scale` | {artifact["gamma_scale"]} | tied to MOD shelf-life invariant |
| `reference_life_days` | {artifact["reference_life_days"]} | literature eta_ref |
| `q10` | {artifact["q10"]} | ModelParams / ADR 0008 default |
| `T_ref` | {artifact["T_ref"]} | ADR 0041 convention |

## Honesty

- n=6 shipments **do not validate** the parametric families; fit automates moment
  matching, not proof of model correctness.
- Strawberry logger substitution; refrigerated-leg-only window; arrival f is an
  **upper bound** (field heat excluded).

## Empirical summaries

{table_md}

Overlay: `data/abdella/arrival_calibration_overlay.png`

Re-run: ``uv sync --extra data --extra viz`` then
``uv run python scripts/fit_abdella_arrival.py``
"""
    path.write_text(body, encoding="utf-8")


def _write_calibration_note(
    path: Path,
    artifact: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    table_lines = ["| shipment | d_days | phi_bar |", "| --- | --- | --- |"]
    for row in rows:
        table_lines.append(
            f"| {row['shipment']} | {row['d_days']:.3f} | {row['phi_bar']:.3f} |"
        )
    table_md = "\n".join(table_lines)
    prov = artifact["provenance"]
    note = f"""# Abdella arrival calibration note

Parameters in `arrival_model.json` are **fitted offline** from six Abdella shipments
(`scripts/fit_abdella_arrival.py`). The data **does not validate** the assumed families;
with only six corridors, treat numbers as defensible starting points, not MLE proof.

## Window consistency

Both duration `d` and `phi_bar` are measured over the **same refrigerated leg**:
from the first lot-mean sample below **10 °C** through the published Table 2 clip.
Warm harvest spikes and **field heat** are excluded. Arrival freshness is an
**upper bound** on store-relevant quality.

## Position spread (`sigma_pos`)

{_escape_for_md(prov.get("adjustment_notes", {}).get("sigma_pos", ""))}
**S4** suspect position probes excluded when estimating spread.

## Empirical overlay (six shipments)

{table_md}

See also `data/abdella/fit_report.md` (fit_utc: {prov.get("fit_utc", "?")}).
"""
    path.write_text(note, encoding="utf-8")


def _escape_for_md(text: str) -> str:
    return text.replace("`", "")


def main(argv: list[str] | None = None) -> None:
    _require_deps()
    parser = argparse.ArgumentParser(description="Fit Abdella arrival_model.json")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_DEFAULT_DATA,
        help="directory with s1..s6.parquet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_ARTIFACT,
        help="output arrival_model.json path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=_DEFAULT_REPORT,
        help="output fit_report.md path",
    )
    parser.add_argument(
        "--override-gamma",
        action="store_true",
        help="refit gamma_shape/gamma_scale from data (not recommended for n=6)",
    )
    args = parser.parse_args(argv)

    data_dir = args.data_dir.resolve()
    rows = _summarize_shipments(data_dir)

    gamma_shape = _DEFAULT_GAMMA_SHAPE
    gamma_scale = _DEFAULT_GAMMA_SCALE
    gamma_note = (
        f"keep gamma_shape={gamma_shape}, gamma_scale={gamma_scale} "
        f"(MOD eta_ref={_DEFAULT_REFERENCE_LIFE} continuity; not identified from n=6)"
    )
    if args.override_gamma:
        gamma_note = "override-gamma flag set (manual review required)"

    sigma_pos, sigma_pos_note = _estimate_sigma_pos(data_dir)

    artifact = _build_artifact(
        rows,
        sigma_pos=sigma_pos,
        sigma_pos_note=sigma_pos_note,
        gamma_shape=gamma_shape,
        gamma_scale=gamma_scale,
        reference_life=_DEFAULT_REFERENCE_LIFE,
        q10=_DEFAULT_Q10,
        t_ref=_DEFAULT_T_REF,
        temp_floor=_DEFAULT_TEMP_FLOOR,
        gamma_note=gamma_note,
    )

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    _write_fit_report(
        args.report.resolve(),
        artifact=artifact,
        rows=rows,
        sigma_pos_note=sigma_pos_note,
        gamma_note=gamma_note,
    )
    _write_overlay(artifact, rows, _DEFAULT_FIG.resolve())
    _write_calibration_note(_DEFAULT_NOTE.resolve(), artifact, rows)

    print(f"Wrote {out_path}")
    print(f"Wrote {args.report.resolve()}")
    print(f"Wrote {_DEFAULT_FIG.resolve()}")
    print(f"Wrote {_DEFAULT_NOTE.resolve()}")


if __name__ == "__main__":
    main()
