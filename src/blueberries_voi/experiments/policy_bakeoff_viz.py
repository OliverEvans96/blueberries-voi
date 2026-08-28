"""Policy / controller bakeoff figure writers (notebooks 20-21)."""

from __future__ import annotations

from statistics import mean
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


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
