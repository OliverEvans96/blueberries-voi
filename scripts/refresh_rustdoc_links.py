#!/usr/bin/env python3
"""Refresh rustdoc markdown links from the manifest (fixes stale URLs)."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
MANIFEST_PATH = DOCS_ROOT / ".vitepress" / "rustdoc-manifest.json"

ROW_RE = re.compile(
    r"(`crates/voi_core/src/(?P<module>[a-z_]+)\.rs(?::[\d,-]+)?`\s*)"
    r"(?:\(`(?P<symbol>[^`]+)`\)|\(\[`(?P<symbol_linked>[^`]+)`\]\(/api/rust/[^)]+\)\))"
)


def main() -> int:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    link_map = {
        (e["module"], e["symbol"]): f"/api/rust/{e['rustdoc_path']}"
        for e in data["entries"]
        if e.get("linkable")
    }
    n = 0
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        if "node_modules" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")

        def repl(m: re.Match[str]) -> str:
            prefix = m.group(1)
            sym = (m.group("symbol") or m.group("symbol_linked") or "").strip()
            url = link_map.get((m.group("module"), sym))
            if url is None:
                return m.group(0)
            return f"{prefix}([`{sym}`]({url}))"

        new_text = ROW_RE.sub(repl, text)
        if new_text != text:
            md.write_text(new_text, encoding="utf-8")
            n += 1
            print(md.relative_to(REPO_ROOT))
    print(f"refreshed {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
