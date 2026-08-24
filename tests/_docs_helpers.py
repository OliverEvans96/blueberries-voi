"""Shared helpers for the docs guard tests (tests/test_docs_*.py).

Stdlib-only: no PyYAML/ruamel dependency. Parses the light `key: value` /
`key: [a, b]` / `key:\n  - a\n  - b` frontmatter shape actually used under
docs/**/*.md. This is NOT a general YAML parser -- it only needs to handle
the handful of shapes this repo's docs frontmatter uses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"

DOCS_SKIP_DIRS = {
    DOCS_ROOT / ".vitepress",
    DOCS_ROOT / "node_modules",
    DOCS_ROOT / "public",
}


def iter_doc_files() -> list[Path]:
    """All docs/**/*.md files, skipping .vitepress/, node_modules/, public/."""
    out: list[Path] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        if any(skip in path.parents for skip in DOCS_SKIP_DIRS):
            continue
        out.append(path)
    return out


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file's text into (frontmatter_block, body).

    The frontmatter block is the raw text between the leading `---` delimiters
    (not including the delimiter lines themselves). If there is no leading
    `---` block, frontmatter is "" and body is the whole text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            return frontmatter, body
    # Unterminated frontmatter block: treat whole thing as body to be safe.
    return "", text


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    return raw.strip("'\"")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Hand-rolled parser for this repo's simple frontmatter shape.

    Supports:
        key: value
        key: [a, b, c]
        key:
          nested: value
          nested2: [a, b]
        key:
          - a
          - b

    Returns a dict whose top-level values are either strings, lists of
    strings, or nested dicts (one level deep is all this repo uses).
    """
    frontmatter, _ = split_frontmatter(text)
    result: dict[str, Any] = {}
    if not frontmatter.strip():
        return result

    raw_lines = frontmatter.splitlines()
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent != 0:
            # Should have been consumed by nested-block handling below.
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest:
            result[key] = _parse_scalar(rest)
            i += 1
            continue

        # Nested block: collect subsequent more-indented lines.
        block: list[str] = []
        j = i + 1
        while j < len(raw_lines):
            nxt = raw_lines[j]
            if not nxt.strip():
                j += 1
                continue
            nxt_indent = len(nxt) - len(nxt.lstrip(" "))
            if nxt_indent <= indent:
                break
            block.append(nxt)
            j += 1

        if block and block[0].lstrip().startswith("- "):
            # A plain YAML list under `key:`.
            result[key] = [
                b.lstrip()[2:].strip().strip("'\"")
                for b in block
                if b.lstrip().startswith("- ")
            ]
        else:
            nested: dict[str, Any] = {}
            for b in block:
                if ":" not in b:
                    continue
                nkey, _, nrest = b.partition(":")
                nkey = nkey.strip()
                nrest = nrest.strip()
                if nrest:
                    nested[nkey] = _parse_scalar(nrest)
                else:
                    # A list-of-scalars nested one level further (key:\n  - a).
                    nested_indent = len(b) - len(b.lstrip(" "))
                    sub_items = []
                    k = block.index(b) + 1
                    while k < len(block):
                        sb = block[k]
                        sb_indent = len(sb) - len(sb.lstrip(" "))
                        if sb_indent <= nested_indent:
                            break
                        if sb.lstrip().startswith("- "):
                            sub_items.append(sb.lstrip()[2:].strip().strip("'\""))
                        k += 1
                    nested[nkey] = sub_items
            result[key] = nested
        i = j
    return result


def frontmatter_adr_numbers(text: str) -> list[str]:
    """Extract `sources: adr: [...]` ADR numbers as 4-digit zero-padded strings."""
    fm = parse_frontmatter(text)
    sources = fm.get("sources")
    if not isinstance(sources, dict):
        return []
    adr = sources.get("adr")
    if not isinstance(adr, list):
        return []
    out = []
    for item in adr:
        item = str(item).strip()
        if not item:
            continue
        digits = item.zfill(4) if item.isdigit() else item
        out.append(digits)
    return out
