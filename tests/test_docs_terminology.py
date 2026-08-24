"""T-150 docs guard: banned legacy terminology must not appear in docs body text.

Mirrors the spirit of crates/voi_core/tests/t150_phase1_terminology.rs -- a
grep-based guard with clear file:line failure messages -- but scoped to the
VitePress docs site (docs/**/*.md) instead of the Rust/TS source tree.

Retired terms (case-insensitive):
    age_at_receipt, effective age, arrival age, age marginal, age composition

Frontmatter YAML is exempt (it's metadata, e.g. ADR/code citations, not prose).
A line is also exempt if it is clearly *explaining* the retired term as
history/legacy (contains "legacy" or "retired" on the same line) -- this
lets a page like "freshness, not age" say "the retired term `effective age`
used to mean X" without tripping the guard.

Backtick-quoted spans and markdown table rows under ``## In the code`` are also
exempt -- those cite symbols and guard tests, not user-facing prose.
"""

from __future__ import annotations

import re

import pytest

from _docs_helpers import iter_doc_files, split_frontmatter

pytestmark = pytest.mark.docs

BANNED_SUBSTRINGS = [
    "age_at_receipt",
    "effective age",
    "arrival age",
    "age marginal",
    "age composition",
]

ALLOW_MARKERS = ("legacy", "retired")
IN_THE_CODE_HEADING = "## In the code"
BACKTICK_RE = re.compile(r"`[^`]*`")
DOUBLE_QUOTED_RE = re.compile(r'"[^"]*"')


def _line_offset_of_body(text: str) -> int:
    """Number of lines occupied by the frontmatter block + its `---` delimiters."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    return 0


def _strip_backticks(line: str) -> str:
    line = BACKTICK_RE.sub("", line)
    return DOUBLE_QUOTED_RE.sub("", line)


def _in_the_code_table_rows(body: str) -> set[int]:
    """1-indexed body line numbers that are table rows under ``## In the code``."""
    lines = body.splitlines()
    in_section = False
    rows: set[int] = set()
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped == IN_THE_CODE_HEADING:
            in_section = True
            continue
        if (
            in_section
            and stripped.startswith("## ")
            and stripped != IN_THE_CODE_HEADING
        ):
            in_section = False
            continue
        if in_section and stripped.startswith("|") and stripped.endswith("|"):
            rows.add(line_no)
    return rows


def _find_banned_hits(path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    _, body = split_frontmatter(text)
    offset = _line_offset_of_body(text)
    code_table_rows = _in_the_code_table_rows(body)

    hits: list[str] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        if line_no in code_table_rows:
            continue
        scan_line = _strip_backticks(line)
        lowered = scan_line.lower()
        if any(marker in lowered for marker in ALLOW_MARKERS):
            continue
        for banned in BANNED_SUBSTRINGS:
            if banned in lowered:
                abs_line = line_no + offset
                hits.append(f"{path}:{abs_line}: [{banned}] {line.strip()}")
    return hits


def test_no_banned_terminology_in_docs_body() -> None:
    all_hits: list[str] = []
    for path in iter_doc_files():
        all_hits.extend(_find_banned_hits(path))

    assert not all_hits, (
        "T-150 docs terminology guard: retired terms found in docs body text "
        "(banned: " + ", ".join(BANNED_SUBSTRINGS) + "). "
        "If this is a deliberate legacy/history reference, add the word "
        "'legacy' or 'retired' on the same line to allowlist it:\n"
        + "\n".join(all_hits)
    )


def test_banned_substring_list_is_lowercase_and_nonempty() -> None:
    # Sanity check on the guard's own config -- catches a future edit that
    # accidentally breaks the case-insensitive matching above.
    assert BANNED_SUBSTRINGS
    for s in BANNED_SUBSTRINGS:
        assert s == s.lower()
        assert re.match(r"^[a-z0-9_ ]+$", s)
