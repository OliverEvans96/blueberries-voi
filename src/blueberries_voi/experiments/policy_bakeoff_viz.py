"""Policy bakeoff figure writers (T-164 notebook 20)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write_runtime_frontier_figure(out_path: Path, rows: list[dict[str, float]]) -> None:
    """Write a minimal JSON artifact for runtime vs accuracy frontier plots."""
    import json

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")
