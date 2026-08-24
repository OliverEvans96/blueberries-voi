#!/usr/bin/env python3
"""Insert stub /// doc comments on voi_core symbols cited by the docs manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / ".vitepress" / "rustdoc-manifest.json"
VOI_CORE_SRC = REPO_ROOT / "crates" / "voi_core" / "src"

STUB = """/// Stub API reference — full narrative is on the VitePress docs site.
///
/// See the concept pages that cite this symbol in their "In the code" tables.
"""


def _has_doc_above(lines: list[str], idx: int) -> bool:
    j = idx - 1
    while j >= 0 and lines[j].strip() == "":
        j -= 1
    if j < 0:
        return False
    return lines[j].lstrip().startswith("///") or lines[j].lstrip().startswith("//!")


def _insert_stub(path: Path, pattern: str) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = False
    rx = re.compile(pattern)
    i = 0
    while i < len(lines):
        if rx.search(lines[i]) and not _has_doc_above(lines, i):
            indent = re.match(r"^(\s*)", lines[i]).group(1)
            stub_lines = [indent + line + "\n" for line in STUB.strip().split("\n")]
            lines[i:i] = stub_lines
            changed = True
            i += len(stub_lines)
        i += 1
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    touched = 0
    for entry in data["entries"]:
        module = entry["module"]
        symbol = entry["symbol"]
        path = VOI_CORE_SRC / f"{module}.rs"
        if not path.is_file():
            continue
        if "::" in symbol:
            _ty, method = symbol.split("::", 1)
            method = method.split("(")[0]
            pat = rf"^\s*pub\s+fn\s+{re.escape(method)}\b"
        else:
            base = symbol.rstrip("()")
            pat = (
                rf"^\s*pub\s+(?:fn|struct|enum|const|type)\s+{re.escape(base)}\b|"
                rf"^\s*fn\s+{re.escape(base)}\b"
            )
        if _insert_stub(path, pat):
            print(f"stubbed {symbol} in {path.relative_to(REPO_ROOT)}")
            touched += 1
    print(f"Done: {touched} symbol(s) stubbed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
