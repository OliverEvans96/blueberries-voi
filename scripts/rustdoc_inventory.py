#!/usr/bin/env python3
"""Build rustdoc cross-link manifest from VitePress docs citations.

Scans docs/**/*.md for `` `crates/voi_core/src/{module}.rs:…` (`symbol`) `` rows,
maps each linkable symbol to a rustdoc HTML path under /api/rust/voi_core/, and
writes docs/.vitepress/rustdoc-manifest.json.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
LIB_RS = REPO_ROOT / "crates" / "voi_core" / "src" / "lib.rs"
VOI_CORE_SRC = REPO_ROOT / "crates" / "voi_core" / "src"
MANIFEST_PATH = DOCS_ROOT / ".vitepress" / "rustdoc-manifest.json"

CITATION_RE = re.compile(
    r"`crates/voi_core/src/(?P<module>[a-z_]+)\.rs(?::[\d,-]+)?`\s*"
    r"(?:\(`(?P<symbol>[^`]+)`\)|\(\[`(?P<symbol_linked>[^`]+)`\]\(/api/rust/[^)]+\)\))"
)

SYMBOL_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?$"
)

PUB_USE_RE = re.compile(
    r"pub use (?P<module>[a-z_]+)::\{([^}]+)\}|"
    r"pub use (?P<module2>[a-z_]+)::(?P<single>[A-Za-z_][A-Za-z0-9_]*)"
)


@dataclass(frozen=True)
class ManifestEntry:
    symbol: str
    module: str
    source_file: str
    rustdoc_path: str
    linkable: bool
    # nearest public symbol when linkable is false (optional)
    link_target: str | None = None


def _parse_crate_root_exports() -> set[str]:
    text = LIB_RS.read_text(encoding="utf-8")
    exports: set[str] = set()
    # Flatten multiline `pub use foo::{ a, b, c };` blocks.
    flat = re.sub(r"\s+", " ", text)
    for m in re.finditer(r"pub use ([a-z_]+)::\{([^}]+)\}", flat):
        for item in m.group(2).split(","):
            name = item.strip().split("::")[-1]
            if name:
                exports.add(name)
    for m in re.finditer(r"pub use ([a-z_]+)::([A-Za-z_][A-Za-z0-9_]*);", flat):
        exports.add(m.group(2))
    return exports


def _impl_type_for_method(text: str, method: str) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not re.search(rf"^\s*pub\s+fn\s+{re.escape(method)}\b", line):
            continue
        # Module-level `pub fn` (column 0) is never an impl method.
        if re.match(r"^pub\s+fn\s", line):
            return None
        for j in range(i, -1, -1):
            m = re.match(r"^impl(?:<[^>]+>)?\s+(\w+)", lines[j].strip())
            if m:
                return m.group(1)
            m = re.match(r"^impl(?:<[^>]+>)?\s+\w+\s+for\s+(\w+)", lines[j].strip())
            if m:
                return m.group(1)
    return None


def _rustdoc_path(module: str, symbol: str, _crate_root: set[str]) -> str:
    """Rustdoc pages live under the defining module, not crate-root re-exports."""
    path = VOI_CORE_SRC / f"{module}.rs"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "::" in symbol:
        ty, method = symbol.split("::", 1)
        method = method.split("(")[0]
        return f"voi_core/{module}/struct.{ty}.html#method.{method}"
    base = symbol.rstrip("()")
    owner = _impl_type_for_method(text, base)
    if owner is not None:
        return f"voi_core/{module}/struct.{owner}.html#method.{base}"
    if re.search(rf"\bpub\s+struct\s+{re.escape(base)}\b", text):
        return f"voi_core/{module}/struct.{base}.html"
    if re.search(rf"\bpub\s+enum\s+{re.escape(base)}\b", text):
        return f"voi_core/{module}/enum.{base}.html"
    if re.search(rf"\bpub\s+const\s+{re.escape(base)}\b", text):
        return f"voi_core/{module}/constant.{base}.html"
    return f"voi_core/{module}/fn.{base}.html"


def _is_public_symbol(module: str, symbol: str) -> bool:
    """True when the symbol appears in rustdoc output (public API)."""
    path = VOI_CORE_SRC / f"{module}.rs"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    base = symbol.split("::")[-1].rstrip("()")
    if "::" in symbol:
        ty, method = symbol.split("::", 1)
        method = method.split("(")[0]
        if not re.search(rf"\bpub\s+struct\s+{re.escape(ty)}\b", text):
            return False
        return bool(re.search(rf"\bpub\s+fn\s+{re.escape(method)}\b", text)) or bool(
            re.search(rf"\bfn\s+{re.escape(method)}\b", text)
        )
    if _impl_type_for_method(text, base) is not None:
        return True
    patterns = [
        rf"\bpub\s+fn\s+{re.escape(base)}\b",
        rf"\bpub\s+struct\s+{re.escape(base)}\b",
        rf"\bpub\s+enum\s+{re.escape(base)}\b",
        rf"\bpub\s+const\s+{re.escape(base)}\b",
        rf"\bpub\s+type\s+{re.escape(base)}\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _collect_citations() -> dict[tuple[str, str], str]:
    """(module, symbol) -> first source_file path in docs."""
    found: dict[tuple[str, str], str] = {}
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        if "node_modules" in md.parts:
            continue
        rel = md.relative_to(DOCS_ROOT).as_posix()
        for m in CITATION_RE.finditer(md.read_text(encoding="utf-8")):
            sym = (m.group("symbol") or m.group("symbol_linked") or "").strip()
            if not SYMBOL_RE.match(sym):
                continue
            key = (m.group("module"), sym)
            found.setdefault(key, rel)
    return found


def build_manifest() -> list[ManifestEntry]:
    crate_root = _parse_crate_root_exports()
    citations = _collect_citations()
    entries: list[ManifestEntry] = []
    for (module, symbol), _doc_page in sorted(citations.items()):
        source = f"crates/voi_core/src/{module}.rs"
        linkable = _is_public_symbol(module, symbol)
        path = _rustdoc_path(module, symbol, crate_root)
        entries.append(
            ManifestEntry(
                symbol=symbol,
                module=module,
                source_file=source,
                rustdoc_path=path,
                linkable=linkable,
                link_target=path if linkable else None,
            )
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write manifest JSON")
    parser.add_argument("--check", action="store_true", help="Fail if manifest stale")
    args = parser.parse_args()

    entries = build_manifest()
    payload = {
        "generated_by": "scripts/rustdoc_inventory.py",
        "entries": [asdict(e) for e in entries],
    }
    new_json = json.dumps(payload, indent=2) + "\n"

    if args.write:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(new_json, encoding="utf-8")
        print(f"Wrote {len(entries)} entries to {MANIFEST_PATH}")
        return 0

    if args.check:
        if not MANIFEST_PATH.is_file():
            print(f"Missing {MANIFEST_PATH}; run with --write")
            return 1
        if MANIFEST_PATH.read_text(encoding="utf-8") != new_json:
            print(f"Stale {MANIFEST_PATH}; run scripts/rustdoc_inventory.py --write")
            return 1
        print(f"Manifest OK ({len(entries)} entries)")
        return 0

    print(new_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
