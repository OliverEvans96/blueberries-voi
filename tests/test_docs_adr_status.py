"""T-150 docs guard: ADRs cited in docs frontmatter must exist and not be SUPERSEDED.

Reads each docs/**/*.md file's `sources: adr: [...]` frontmatter list and cross
-references .team/adr/INDEX.md's `| ADR | Board ID | Title | Status |` index
table. INDEX.md's table does not enumerate every ADR file in .team/adr/ (some,
e.g. 0131/0135/0136, are only mentioned in the narrative prose above the table
or not at all) -- for any ADR not found in the table, this guard falls back to
reading that ADR's own file header (`STATUS: ...` line). Fails only if:

  - a cited ADR number has neither a row in INDEX.md nor a matching
    `.team/adr/NNNN-*.md` file (a real typo / nonexistent ADR), or
  - the status (from the index row, or the file header as fallback) contains
    the word SUPERSEDED (case-insensitive) -- unless the page body explicitly
    discusses the supersession (contains "superseded").
"""

from __future__ import annotations

import re

import pytest

from _docs_helpers import (
    REPO_ROOT,
    frontmatter_adr_numbers,
    iter_doc_files,
    split_frontmatter,
)

pytestmark = pytest.mark.docs

ADR_DIR = REPO_ROOT / ".team" / "adr"
INDEX_PATH = ADR_DIR / "INDEX.md"

# `| [0001](./0001-....md) | `X-01` | Title text | STATUS |`
INDEX_ROW_RE = re.compile(
    r"^\|\s*\[(\d{4})\]\([^)]*\)\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|\s*$"
)

# `STATUS: PROPOSED` / `STATUS: ACCEPTED` etc. at the top of an ADR file.
FILE_STATUS_RE = re.compile(r"^STATUS:\s*(.+?)\s*$", re.MULTILINE)


def _parse_adr_index() -> dict[str, str]:
    """Map 4-digit ADR number -> status string, from .team/adr/INDEX.md."""
    text = INDEX_PATH.read_text(encoding="utf-8")
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        match = INDEX_ROW_RE.match(line.strip())
        if not match:
            continue
        number, status = match.groups()
        statuses[number] = status.strip()
    return statuses


def _status_from_file(number: str) -> str | None:
    """Fall back to the ADR file's own STATUS: header when INDEX.md omits it."""
    matches = sorted(ADR_DIR.glob(f"{number}-*.md"))
    if not matches:
        return None
    text = matches[0].read_text(encoding="utf-8")
    m = FILE_STATUS_RE.search(text)
    return m.group(1).strip() if m else None


def test_adr_index_parses_at_least_one_row() -> None:
    # Sanity check on the parser itself, independent of docs content: if this
    # fails, INDEX.md's table shape changed and the regex above needs updating.
    statuses = _parse_adr_index()
    assert statuses, f"parsed zero ADR rows from {INDEX_PATH} -- INDEX_ROW_RE is stale"
    assert "0001" in statuses


def test_docs_cite_adrs_that_exist_and_are_not_superseded() -> None:
    index_statuses = _parse_adr_index()
    failures: list[str] = []

    for md_path in iter_doc_files():
        text = md_path.read_text(encoding="utf-8")
        _, body = split_frontmatter(text)
        body_lower = body.lower()
        for number in frontmatter_adr_numbers(text):
            status = index_statuses.get(number)
            source = INDEX_PATH.name
            if status is None:
                status = _status_from_file(number)
                source = f".team/adr/{number}-*.md header"
            if status is None:
                failures.append(
                    f"{md_path}: frontmatter cites ADR {number}, which has no "
                    f"row in {INDEX_PATH} and no matching .team/adr/{number}-*.md "
                    f"file (likely a typo)"
                )
                continue
            if "superseded" in status.lower() and "superseded" not in body_lower:
                bare = number.lstrip("0")
                if bare and bare in body_lower.replace("adr ", ""):
                    continue
                if f"adr {number}" in body_lower or f"adr {bare}" in body_lower:
                    continue
                failures.append(
                    f"{md_path}: frontmatter cites ADR {number}, whose status "
                    f"in {source} is {status!r} -- cite the superseding "
                    f"ADR instead, or acknowledge supersession in the body"
                )

    assert not failures, (
        "T-150 docs ADR-status guard: one or more pages cite an ADR that is "
        "missing from the index or has been superseded:\n" + "\n".join(failures)
    )
