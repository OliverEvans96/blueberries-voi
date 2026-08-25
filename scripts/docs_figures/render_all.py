"""Render every documentation figure into ``docs/public/figures/``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from _paths import OUT
from PIL import Image, ImageDraw, ImageFont

DOCS_FIGURES = Path(__file__).resolve().parent
REPO_ROOT = DOCS_FIGURES.parents[2]
FIGURES_DIR = OUT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(DOCS_FIGURES) not in sys.path:
    sys.path.insert(0, str(DOCS_FIGURES))

MODULES = [
    "store.picking_weights",
    "store.gamma_aging",
    "store.spoilage_trajectories",
    "store.demand_calendar",
    "store.freshness_not_age",
    "store.one_day_timeline",
    "start_here.five_minutes_timeline",
    "start_here.glossary_journey",
    "control.newsvendor",
    "control.protection_demand",
    "control.effective_inventory",
    "control.alpha_tune",
    "economics.profit_waterfall",
    "findings.does_money_follow",
    "inference.belief_wire",
    "inference.birth_freshness",
    "inference.particle_shelf",
    "ladder.channels_grid",
    "ladder.rungs_ladder",
    "ladder.conditioning_tiers",
    "findings.limitations_map",
    "reference.lot_journey",
    "using_it.run_surfaces",
    "using_it.studio_cockpit",
]

CONTACT_SHEET_SKIP = frozenset({"_qa_contact_sheet.png", "_studio_cockpit_raw.png"})


def _build_contact_sheet() -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        p
        for p in FIGURES_DIR.glob("*.png")
        if p.name not in CONTACT_SHEET_SKIP and not p.name.startswith("_")
    )
    if not paths:
        raise RuntimeError("No figures found for contact sheet")

    thumb_w, thumb_h = 320, 200
    cols = 4
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + 24)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, path in enumerate(paths):
        col, row = i % cols, i // cols
        img = Image.open(path)
        img.thumbnail((thumb_w, thumb_h))
        x = col * thumb_w + (thumb_w - img.width) // 2
        y = row * (thumb_h + 24) + 20
        sheet.paste(img, (x, y))
        draw.text(
            (col * thumb_w + 4, row * (thumb_h + 24) + 2),
            path.name,
            fill="black",
            font=font,
        )
    out = FIGURES_DIR / "_qa_contact_sheet.png"
    sheet.save(out)
    return out


def render_all(out_dir: Path | None = None) -> list[Path]:
    target = out_dir or FIGURES_DIR
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for mod_name in MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as err:
            print(f"skip {mod_name}: {err}")
            continue
        print(f"rendering {mod_name}...")
        result = mod.render(target)
        if isinstance(result, Path):
            written.append(result)
    contact = _build_contact_sheet()
    written.append(contact)
    print(f"contact sheet: {contact}")
    return written


def main() -> None:
    print(f"Rendering doc figures to {FIGURES_DIR.relative_to(REPO_ROOT)} …")
    paths = render_all()
    for path in paths:
        print(f"  wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
