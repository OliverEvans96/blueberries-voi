"""Regenerate notebook 13 figures from a Modal shard JSON (no engine replay)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
FIG_DIR = REPO / "figures" / "filter_accuracy"
DATA = REPO / "experiments" / "data"
LADDER_ORDER = ["P0", "P1", "F1", "F1s", "F2a", "F2", "F3"]
PRIMARY_SEED = 42
POS_OPTS = ("upc_only", "lot_id")
WASTE_OPTS = ("none", "daily_counts", "lot_id")
DEL_OPTS = ("quantity_only", "pack_date_per_lot")

SCENARIO_LABELS = {
    "P0": "P0 · books only",
    "P1": "P1 · + waste totals",
    "F1": "F1 · + lot sales",
    "F1s": "F1s · + lot waste",
    "F2a": "F2a · + pack date",
    "F2": "F2 · + pack date (LGTIN bundle)",
    "F3": "F3 · + temperature trace (Λ)",
}
SCENARIO_COLORS = {
    "P0": "#8c8c8c",
    "P1": "#4c72b0",
    "F1": "#dd8452",
    "F1s": "#c44e52",
    "F2a": "#55a868",
    "F2": "#8172b3",
    "F3": "#2ca02c",
}


def _load() -> tuple[list[dict], list[dict]]:
    rows = json.loads((DATA / "nb13_channel_rows.json").read_text())
    shards = json.loads((DATA / "nb13_channel_rows_shards.json").read_text())
    return rows, shards


def _pivot(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    named = df[df["preset"].isin(LADDER_ORDER)]
    pivot = (
        named.groupby("preset")[["mae_f", "mean_spread"]]
        .mean()
        .reindex([s for s in LADDER_ORDER if s in set(named["preset"])])
    )
    return pivot


def plot_accuracy_ladder(pivot_df: pd.DataFrame) -> Path:
    order = list(pivot_df.index)
    fig, ax = plt.subplots(figsize=(8, 5))
    mae = pivot_df["mae_f"].values
    colors = [SCENARIO_COLORS[s] for s in order]
    y = np.arange(len(order))
    bars = ax.barh(y, mae, color=colors, edgecolor="0.2", linewidth=0.6)
    p0 = float(pivot_df.loc["P0", "mae_f"])
    ax.axvline(p0, color="0.45", ls="--", lw=1.2, label="P0 baseline")
    for bar, val, sc in zip(bars, mae, order, strict=True):
        ax.text(
            val + 0.008,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}",
            va="center",
            fontsize=9,
        )
        ax.text(
            0.01,
            bar.get_y() + bar.get_height() / 2,
            SCENARIO_LABELS[sc],
            va="center",
            fontsize=8,
            color="0.25",
        )
    ax.set_yticks([])
    ax.set_xlabel("Mean |belief - truth| on shelf mean f  (lower is better)")
    ax.set_title("Filter accuracy ladder - shared physics (T-150, damped SW)")
    ax.set_xlim(0, max(mae) * 1.25)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    out = FIG_DIR / "accuracy_ladder_mae_f.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_waterfall(pivot_df: pd.DataFrame) -> Path:
    chain = [s for s in ["P0", "P1", "F2a", "F2", "F3"] if s in pivot_df.index]
    vals = [float(pivot_df.loc[s, "mae_f"]) for s in chain]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(chain, vals, "o-", color="#4c72b0", lw=2, markersize=8)
    for i in range(1, len(chain)):
        drop = vals[i - 1] - vals[i]
        ax.annotate(
            f"{drop:+.3f}",
            xy=(chain[i], vals[i]),
            xytext=(8, 12),
            textcoords="offset points",
            fontsize=9,
            color="#55a868" if drop > 0 else "#c44e52",
        )
    ax.set_ylabel("MAE(mean f)")
    ax.set_title("Accuracy along the arrival ladder (T-150)")
    ax.set_ylim(0, max(vals) * 1.15)
    fig.tight_layout()
    out = FIG_DIR / "accuracy_waterfall_chain.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_accuracy_vs_uncertainty(pivot_df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 5))
    for sc in pivot_df.index:
        ax.scatter(
            pivot_df.loc[sc, "mean_spread"],
            pivot_df.loc[sc, "mae_f"],
            s=120,
            color=SCENARIO_COLORS[sc],
            edgecolor="0.2",
            label=sc,
        )
        ax.annotate(
            sc,
            (pivot_df.loc[sc, "mean_spread"], pivot_df.loc[sc, "mae_f"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=9,
        )
    ax.set_xlabel("Posterior spread (f) — wider = more uncertain")
    ax.set_ylabel("MAE(mean f) — lower = more accurate")
    ax.set_title("Accuracy vs uncertainty tradeoff")
    fig.tight_layout()
    out = FIG_DIR / "accuracy_vs_spread.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_tracks(shards: list[dict], seed: int = PRIMARY_SEED) -> Path:
    by_preset = {s["preset"]: s for s in shards if s["seed"] == seed}
    focus = [s for s in ("P0", "P1", "F2", "F3") if s in by_preset]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for sc in focus:
        days = by_preset[sc]["days"]
        t = [d["episode_day"] for d in days]
        axes[0].plot(
            t,
            [d["truth_f"] for d in days],
            ":",
            color=SCENARIO_COLORS[sc],
            alpha=0.5,
        )
        axes[0].plot(
            t,
            [d["belief_f"] for d in days],
            "-",
            color=SCENARIO_COLORS[sc],
            lw=2,
            label=SCENARIO_LABELS[sc],
        )
        axes[1].plot(
            t,
            [d["abs_f_err"] for d in days],
            "-o",
            color=SCENARIO_COLORS[sc],
            ms=3,
            lw=1.5,
            label=sc,
        )
    axes[0].plot([], [], ":", color="0.5", label="truth (dotted)")
    axes[0].set_ylabel("Shelf mean freshness f")
    axes[0].set_title(f"Belief tracks truth · seed={seed} · shared orders")
    axes[0].legend(frameon=False, ncol=2, fontsize=8)
    axes[1].set_ylabel("|belief - truth|")
    axes[1].set_xlabel("Episode day")
    axes[1].legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    out = FIG_DIR / "truth_vs_belief_tracks.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_waste_contraction(shards: list[dict], seed: int = PRIMARY_SEED) -> Path:
    p1 = next(s for s in shards if s["seed"] == seed and s["preset"] == "P1")
    days = p1["days"]
    groups = {
        "waste > 0": [d["abs_f_err"] for d in days if d["waste_total"] > 0],
        "no waste": [d["abs_f_err"] for d in days if d["waste_total"] == 0],
    }
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = list(groups.keys())
    means = [float(np.mean(groups[k])) if groups[k] else float("nan") for k in labels]
    ax.bar(labels, means, color=["#55a868", "#c44e52"], alpha=0.85)
    ax.set_ylabel("MAE(mean f)")
    ax.set_title(f"P1: shrink signal vs no-shrink days (seed={seed})")
    for i, m in enumerate(means):
        if np.isfinite(m):
            ax.text(i, m + 0.01, f"{m:.3f}", ha="center", fontsize=10)
    fig.tight_layout()
    out = FIG_DIR / "waste_contraction_p1.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_channel_heatmaps(channel_pivot_df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    waste_labels = list(WASTE_OPTS)
    pos_labels = list(POS_OPTS)
    im = None
    for ax, deliv in zip(axes, DEL_OPTS, strict=True):
        sub = channel_pivot_df[channel_pivot_df["deliveries"] == deliv]
        grid = np.zeros((len(pos_labels), len(waste_labels)))
        for i, pos in enumerate(pos_labels):
            for j, waste in enumerate(waste_labels):
                row = sub[(sub["pos"] == pos) & (sub["waste"] == waste)]
                grid[i, j] = float(row["mae_f"].iloc[0]) if len(row) else np.nan
        im = ax.imshow(
            grid,
            cmap="RdYlGn_r",
            vmin=channel_pivot_df["mae_f"].min(),
            vmax=channel_pivot_df["mae_f"].max(),
        )
        ax.set_xticks(range(len(waste_labels)), waste_labels, rotation=25, ha="right")
        ax.set_yticks(range(len(pos_labels)), pos_labels)
        ax.set_title(f"ASN = {deliv}")
        for i in range(len(pos_labels)):
            for j in range(len(waste_labels)):
                val = grid[i, j]
                hit = sub[
                    (sub["pos"] == pos_labels[i]) & (sub["waste"] == waste_labels[j])
                ]
                preset = hit["preset"].iloc[0] if len(hit) else "custom"
                star = "★" if preset not in ("custom", "F3") else ""
                ax.text(
                    j,
                    i,
                    f"{val:.3f}{star}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="black",
                )
    fig.colorbar(im, ax=axes.ravel().tolist(), label="MAE(mean f)", shrink=0.9)
    fig.suptitle("Channel combinations (★ = named preset)", y=1.02)
    fig.tight_layout()
    out = FIG_DIR / "channel_factorial_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_all_combos_ranked(channel_pivot_df: pd.DataFrame) -> Path:
    df = channel_pivot_df.sort_values("mae_f")
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#8172b3" if p not in ("custom",) else "#b0b0b0" for p in df["preset"]]
    y = np.arange(len(df))
    ax.barh(y, df["mae_f"], color=colors, edgecolor="0.25", linewidth=0.4)
    for i, row in enumerate(df.itertuples()):
        tag = row.preset if row.preset != "custom" else "hybrid"
        ax.text(row.mae_f + 0.005, i, f"{tag}", va="center", fontsize=8)
    ax.set_yticks(
        y,
        [f"{r.pos}/{r.waste}/{r.deliveries}" for r in df.itertuples()],
        fontsize=8,
    )
    ax.set_xlabel("MAE(mean f)")
    ax.set_title("Observation setups ranked (purple = named preset)")
    ax.invert_yaxis()
    fig.tight_layout()
    out = FIG_DIR / "channel_combos_ranked.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_sweeps(rows: list[dict], seed: int = PRIMARY_SEED) -> Path:
    seed_rows = [r for r in rows if r["seed"] == seed]

    def mae(pos: str, waste: str, deliveries: str) -> float:
        hit = [
            r
            for r in seed_rows
            if r["pos"] == pos and r["waste"] == waste and r["deliveries"] == deliveries
        ]
        return float(hit[0]["mae_f"]) if hit else float("nan")

    p0 = mae("upc_only", "none", "quantity_only")
    items = [
        ("P0 baseline", p0),
        ("+ daily waste (→ P1)", mae("upc_only", "daily_counts", "quantity_only")),
        ("+ lot POS only", mae("lot_id", "none", "quantity_only")),
        ("+ lot shrink (→ F1s)", mae("lot_id", "lot_id", "quantity_only")),
        ("+ pack date only", mae("upc_only", "none", "pack_date_per_lot")),
        ("+ pack date + lot POS", mae("lot_id", "none", "pack_date_per_lot")),
        ("Full F2 bundle", mae("lot_id", "lot_id", "pack_date_per_lot")),
        ("F3 temperature trace", mae("lot_id", "lot_id", "temperature_history")),
    ]
    labels = [a for a, _ in items]
    vals = [b for _, b in items]
    deltas = [v - p0 for v in vals]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = [
        "#4c72b0" if "baseline" in lbl else "#55a868" if d < 0 else "#c44e52"
        for lbl, d in zip(labels, deltas, strict=True)
    ]
    ax.barh(labels, vals, color=colors, alpha=0.85)
    ax.set_xlabel("MAE(mean f)")
    ax.set_title(f"One-factor sweeps from P0 (seed={seed})")
    fig.tight_layout()
    out = FIG_DIR / "channel_single_factor_sweeps.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rows, shards = _load()
    pivot = _pivot(rows)
    print("Named-ladder MAE(f) mean over seeds:")
    print(pivot.round(4).to_string())
    if "P0" in pivot.index and "F2" in pivot.index:
        p0 = float(pivot.loc["P0", "mae_f"])
        f2 = float(pivot.loc["F2", "mae_f"])
        f3 = float(pivot.loc["F3", "mae_f"]) if "F3" in pivot.index else float("nan")
        print(f"P0/F2 = {p0 / f2:.2f}   F2-F3 = {f2 - f3:.4f}")
    fact = pd.DataFrame(rows)
    fact = fact[fact["deliveries"].isin(DEL_OPTS)]
    channel_pivot = (
        fact.groupby(["pos", "waste", "deliveries", "preset", "key"])
        .agg(mae_f=("mae_f", "mean"), mean_spread=("mean_spread", "mean"))
        .reset_index()
        .sort_values("mae_f")
    )
    written = [
        plot_accuracy_ladder(pivot),
        plot_waterfall(pivot),
        plot_accuracy_vs_uncertainty(pivot),
        plot_tracks(shards),
        plot_waste_contraction(shards),
        plot_channel_heatmaps(channel_pivot),
        plot_all_combos_ranked(channel_pivot),
        plot_sweeps(rows),
    ]
    for path in written:
        print("wrote", path.relative_to(REPO))


if __name__ == "__main__":
    main()
