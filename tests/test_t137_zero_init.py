"""T-137: global zero-init and starting_inv removal guards."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_starting_inv_removed_from_web_types() -> None:
    types_src = (REPO / "web" / "src" / "types.ts").read_text(encoding="utf-8")
    assert "starting_inv" not in types_src


def test_starting_inv_not_in_controls_or_mock() -> None:
    allow = {
        REPO / ".team" / "changelog.md",
        REPO / ".team" / "specs" / "T-137.md",
        REPO / ".team" / "adr" / "0136-zero-init-phantom-belief-remediation.md",
        Path(__file__),
    }
    hits: list[str] = []
    for path in (REPO / "web").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        if path in allow:
            continue
        text = path.read_text(encoding="utf-8")
        if "starting_inv" in text:
            hits.append(str(path.relative_to(REPO)))
    assert hits == [], f"starting_inv must be removed from web: {hits}"


def test_mock_create_initial_state_empty_lots() -> None:
    from blueberries_voi.simulator.belief import empty_flat_belief

    flat = empty_flat_belief(L=2, K=4)
    assert sum(flat["lot_counts"]) == 0.0
