"""Policy / controller bakeoff figure writers (notebooks 20-21)."""

from __future__ import annotations

from statistics import mean, median
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import numpy as np


def write_runtime_frontier_figure(out_path: Path, rows: list[dict[str, float]]) -> None:
    """Write a minimal JSON artifact for runtime vs accuracy frontier plots."""
    import json

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")


def _arm_order(rows: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        arm = str(row["arm_id"])
        if arm not in seen:
            seen.append(arm)
    return seen


def _values_by_arm(rows: list[dict[str, Any]], field: str) -> dict[str, list[float]]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        arm = str(row["arm_id"])
        buckets.setdefault(arm, []).append(float(row[field]))
    return buckets


def summarize_distribution_by_arm(
    rows: list[dict[str, Any]],
    field: str,
    *,
    arms: list[str] | None = None,
) -> Any:
    """Per-arm distribution summary: median, IQR, min, max, mean."""
    import pandas as pd

    order = arms if arms is not None else _arm_order(rows)
    records: list[dict[str, Any]] = []
    by_arm = _values_by_arm(rows, field)
    for arm in order:
        vals = by_arm.get(arm, [])
        if not vals:
            continue
        arr = np.asarray(vals, dtype=float)
        q25, q75 = np.percentile(arr, [25, 75])
        records.append(
            {
                "arm_id": arm,
                "median": float(median(arr)),
                "q25": float(q25),
                "q75": float(q75),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "mean": float(mean(arr)),
                "n": len(arr),
            }
        )
    return pd.DataFrame(records)


def write_metric_boxplot_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    field: str,
    *,
    ylabel: str,
    title: str,
    arms: list[str] | None = None,
) -> None:
    """Box (+ swarm overlay) plot of a metric across seeds per arm."""
    import matplotlib.pyplot as plt

    order = arms if arms is not None else _arm_order(rows)
    by_arm = _values_by_arm(rows, field)
    data = [by_arm.get(arm, []) for arm in order]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    bp = ax.boxplot(data, tick_labels=order, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set(facecolor="lightsteelblue", alpha=0.7)
    for idx, arm in enumerate(order):
        vals = by_arm.get(arm, [])
        if not vals:
            continue
        jitter = np.random.default_rng(0).uniform(-0.08, 0.08, size=len(vals))
        ax.scatter(
            np.full(len(vals), idx + 1) + jitter,
            vals,
            color="black",
            alpha=0.55,
            s=18,
            zorder=3,
        )
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Controller")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_runtime_violin_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    title: str = "Shard wall time distribution by controller",
) -> None:
    """Violin plot of shard runtime per arm."""

    elapsed_key = (
        "elapsed_s"
        if any("elapsed_s" in r for r in rows)
        else ("_elapsed_s" if any("_elapsed_s" in r for r in rows) else "elapsed_s")
    )
    write_metric_boxplot_figure(
        out_path,
        rows,
        elapsed_key,
        ylabel="Seconds",
        title=title,
    )


def write_paired_delta_boxplot_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    field: str,
    *,
    baseline: str = "sw",
    ylabel: str | None = None,
    title: str | None = None,
) -> None:
    """Box/swarm of per-seed paired deltas vs a baseline arm."""
    import matplotlib.pyplot as plt

    by_seed_arm: dict[tuple[int, str], float] = {}
    seeds: list[int] = []
    arms: list[str] = []
    for row in rows:
        seed = int(row["seed"])
        arm = str(row["arm_id"])
        by_seed_arm[(seed, arm)] = float(row[field])
        if seed not in seeds:
            seeds.append(seed)
        if arm not in arms:
            arms.append(arm)
    seeds.sort()
    compare_arms = [a for a in arms if a != baseline]
    if baseline not in arms:
        msg = f"baseline arm {baseline!r} missing from rows"
        raise ValueError(msg)
    deltas: list[list[float]] = []
    for arm in compare_arms:
        arm_deltas = [
            by_seed_arm[(seed, arm)] - by_seed_arm[(seed, baseline)] for seed in seeds
        ]
        deltas.append(arm_deltas)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    bp = ax.boxplot(deltas, tick_labels=compare_arms, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set(facecolor="wheat", alpha=0.7)
    for idx, arm_deltas in enumerate(deltas):
        jitter = np.random.default_rng(1).uniform(-0.08, 0.08, size=len(arm_deltas))
        ax.scatter(
            np.full(len(arm_deltas), idx + 1) + jitter,
            arm_deltas,
            color="black",
            alpha=0.55,
            s=18,
            zorder=3,
        )
    ax.axhline(0.0, color="gray", linewidth=0.8)
    ax.set_ylabel(ylabel or f"{field} delta vs {baseline}")
    ax.set_xlabel("Controller")
    ax.set_title(title or f"Paired {field} delta vs {baseline}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_alpha_vs_observed_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    observed_field: str = "fill_rate",
    title: str | None = None,
) -> None:
    """Scatter tuned target alpha vs observed service metric per shard."""
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))
    for row in rows:
        ax.scatter(
            float(row["alpha"]),
            float(row[observed_field]),
            label=str(row["arm_id"]),
            alpha=0.7,
            s=40,
        )
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles, strict=False))
    ax.legend(by_label.values(), by_label.keys(), fontsize=7, ncol=2)
    ax.set_xlabel("Target service level (tuned alpha)")
    ax.set_ylabel(observed_field.replace("_", " "))
    ax.set_title(title or f"Tuned alpha vs observed {observed_field}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _mean_by_arm(
    rows: list[dict[str, Any]], field: str
) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        arm = str(row["arm_id"])
        buckets.setdefault(arm, []).append(float(row[field]))
    return {arm: mean(vals) for arm, vals in buckets.items()}


def write_profit_bars_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    title: str = "Mean episode profit by controller",
) -> None:
    """Bar chart of mean profit per arm."""
    import matplotlib.pyplot as plt

    arms = _arm_order(rows)
    means = [_mean_by_arm(rows, "profit")[a] for a in arms]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(arms, means, color="steelblue", edgecolor="black")
    ax.set_ylabel("Profit ($)")
    ax.set_xlabel("Controller")
    ax.set_title(title)
    ax.axhline(0.0, color="gray", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_runtime_bars_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    title: str = "Mean shard wall time by controller",
) -> None:
    """Bar chart of mean ``_elapsed_s`` per arm."""
    import matplotlib.pyplot as plt

    arms = _arm_order(rows)
    elapsed_key = (
        "elapsed_s"
        if any("elapsed_s" in r for r in rows)
        else ("_elapsed_s" if any("_elapsed_s" in r for r in rows) else "elapsed_s")
    )
    means = [_mean_by_arm(rows, elapsed_key)[a] for a in arms]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(arms, means, color="darkorange", edgecolor="black")
    ax.set_ylabel("Seconds")
    ax.set_xlabel("Controller")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_waste_stockout_bars_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    title: str = "Mean waste and stockout by controller",
) -> None:
    """Grouped bar chart for waste vs stockout breakdown."""
    import matplotlib.pyplot as plt
    import numpy as np

    arms = _arm_order(rows)
    waste = [_mean_by_arm(rows, "waste")[a] for a in arms]
    stockout = [_mean_by_arm(rows, "stockout")[a] for a in arms]
    x = np.arange(len(arms))
    width = 0.35
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(x - width / 2, waste, width, label="Waste", color="tab:red")
    ax.bar(x + width / 2, stockout, width, label="Stockout", color="tab:purple")
    ax.set_xticks(x)
    ax.set_xticklabels(arms)
    ax.set_ylabel("Units")
    ax.set_xlabel("Controller")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_paired_delta_figure(
    out_path: Path,
    rows: list[dict[str, Any]],
    *,
    baseline: str = "sw",
    title: str | None = None,
) -> None:
    """Per-seed profit delta vs baseline arm (paired bars)."""
    import matplotlib.pyplot as plt
    import numpy as np

    by_seed_arm: dict[tuple[int, str], float] = {}
    seeds: list[int] = []
    arms: list[str] = []
    for row in rows:
        seed = int(row["seed"])
        arm = str(row["arm_id"])
        by_seed_arm[(seed, arm)] = float(row["profit"])
        if seed not in seeds:
            seeds.append(seed)
        if arm not in arms:
            arms.append(arm)
    seeds.sort()
    compare_arms = [a for a in arms if a != baseline]
    if baseline not in arms:
        msg = f"baseline arm {baseline!r} missing from rows"
        raise ValueError(msg)
    deltas: dict[str, list[float]] = {a: [] for a in compare_arms}
    for seed in seeds:
        base_profit = by_seed_arm[(seed, baseline)]
        for arm in compare_arms:
            deltas[arm].append(by_seed_arm[(seed, arm)] - base_profit)
    x = np.arange(len(compare_arms))
    means = [mean(deltas[a]) for a in compare_arms]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["tab:green" if m >= 0 else "tab:red" for m in means]
    ax.bar(x, means, color=colors, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(compare_arms)
    ax.axhline(0.0, color="gray", linewidth=0.8)
    ax.set_ylabel(f"Profit delta vs {baseline}")
    ax.set_xlabel("Controller")
    ax.set_title(title or f"Paired profit delta vs {baseline}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
