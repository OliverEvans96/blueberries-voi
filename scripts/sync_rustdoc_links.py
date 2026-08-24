#!/usr/bin/env python3
"""Rewrite VitePress docs symbol backticks into rustdoc markdown links."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
MANIFEST_PATH = DOCS_ROOT / ".vitepress" / "rustdoc-manifest.json"

CITATION_RE = re.compile(
    r"(`crates/voi_core/src/(?P<module>[a-z_]+)\.rs(?::[\d,-]+)?`\s*)"
    r"(?:\(`(?P<symbol>[^`]+)`\)|\(\[`(?P<symbol_linked>[^`]+)`\]\(/api/rust/[^)]+\)\))"
)

LINKED_RE = re.compile(
    r"\(\[`(?P<symbol>[^`]+)`\]\(/api/rust/[^)]+\)\)"
)


def _load_link_map() -> dict[tuple[str, str], str]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], str] = {}
    for entry in data["entries"]:
        if not entry.get("linkable"):
            continue
        key = (entry["module"], entry["symbol"])
        out[key] = f"/api/rust/{entry['rustdoc_path']}"
    return out


def _sync_file(path: Path, link_map: dict[tuple[str, str], str]) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        if m.group("symbol_linked"):
            return m.group(0)
        prefix = m.group(1)
        module = m.group("module")
        symbol = m.group("symbol")
        url = link_map.get((module, symbol))
        if url is None:
            return m.group(0)
        changed = True
        return f"{prefix}([`{symbol}`]({url}))"

    new_text = CITATION_RE.sub(repl, text)
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed


def main() -> int:
    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"Missing {MANIFEST_PATH}; run rustdoc_inventory.py --write first")
    link_map = _load_link_map()
    n = 0
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        if "node_modules" in md.parts:
            continue
        if _sync_file(md, link_map):
            n += 1
            print(f"updated {md.relative_to(REPO_ROOT)}")
    print(f"Done: {n} file(s) updated, {len(link_map)} linkable symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
