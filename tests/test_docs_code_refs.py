"""T-150 docs guard: 'In the code' table rows must resolve to real files/symbols.

Walks docs/**/*.md, finds markdown table rows that cite a source-tree path
(a backtick-quoted `crates/...`, `src/...`, or `web/...` path, optionally with
a `:LINE` suffix), and checks:

  (a) the path exists relative to the repo root, and
  (b) if the row also names a plain backtick-quoted identifier (e.g.
      `damped_sw_order_f_belief`, `ObsChannels`), that identifier appears
      somewhere in the text of at least one file the row cites.

This is deliberately a simple substring/grep check, not a real markdown table
parser or source-code parser -- good enough to catch a stale/typo'd path or a
renamed symbol without needing a markdown or Rust/Python/TS AST.
"""

from __future__ import annotations

import re

import pytest

from _docs_helpers import REPO_ROOT, iter_doc_files

pytestmark = pytest.mark.docs

# `crates/...`, `src/...`, `web/...` inside backticks, optionally with a `:LINE`,
# `:LINE-LINE`, or `:LINE,LINE` suffix (the suffix, if any, is captured separately
# so it can be stripped before checking the path exists on disk).
PATH_RE = re.compile(r"`((?:crates|src|web)/[^`\s:]+?)(?::([\d,-]+))?`")

# A "plain" backtick-quoted identifier: word chars plus `::` / `.` qualifiers and
# an optional trailing `()`. Deliberately excludes anything with spaces, braces,
# commas, `$`, etc. -- those are descriptive snippets, not a single symbol name,
# and are skipped rather than (mis)checked.
SYMBOL_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?$"
)

# Table separator rows, e.g. `| --- | --- | --- |`.
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")

# Build artifacts: docs may cite the dev copy under web/src/wasm/.
_RETIRED_ARRIVAL_SYMBOLS = frozenset(
    {"mu_t", "sigma_t", "temp_floor_c", "sample_truncated_normal"}
)
_V2_ARRIVAL_SYMBOLS = frozenset(
    {"thermal_nodes", "truth_transit_trace", "t_break", "legs"}
)
_ARRIVAL_SOURCE_PATHS = (
    "crates/voi_core/src/arrival.rs",
    "crates/voi_core/src/shipments.rs",
)
_ARRIVAL_DOC_PATHS = (
    "docs/reference/parameters.md",
    "docs/store/cold-chain-arrival.md",
)

PATH_ALIASES: dict[str, str] = {
    "web/src/wasm": "packaging/wasm/pkg",
    "web/src/wasm/": "packaging/wasm/pkg/",
}
# Paths that may not exist in a clean checkout (WASM build output).
OPTIONAL_BUILD_PATHS = frozenset(PATH_ALIASES.keys()) | frozenset(
    p.rstrip("/") for p in PATH_ALIASES
)


def _resolve_repo_path(rel_path: str):
    """Map doc citations to on-disk paths (including build-artifact aliases)."""
    normalized = rel_path.rstrip("/")
    alias = PATH_ALIASES.get(rel_path) or PATH_ALIASES.get(normalized)
    if alias:
        return REPO_ROOT / alias
    return REPO_ROOT / rel_path


def _all_backtick_spans(row: str) -> list[str]:
    return re.findall(r"`([^`]*)`", row)


def _symbol_candidates(row: str, path_matches: list[str]) -> list[str]:
    """Backtick spans in `row` that look like a plain identifier and aren't a path."""
    candidates = []
    for span in _all_backtick_spans(row):
        if span in path_matches:
            continue
        if any(span.startswith(p) for p in path_matches):
            continue
        if SYMBOL_RE.match(span):
            candidates.append(span.rstrip("()"))
    return candidates


def _table_data_rows(text: str) -> list[tuple[int, str]]:
    """Return (line number, row text) for markdown table rows, minus separators."""
    rows = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        if SEPARATOR_RE.match(stripped):
            continue
        rows.append((line_no, stripped))
    return rows


def _check_file(md_path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    failures: list[str] = []

    for line_no, row in _table_data_rows(text):
        if not PATH_RE.search(row):
            continue

        skip_symbols = "legacy" in row.lower() or "guard test" in row.lower()

        # Rows commonly cite several unrelated (path, symbol) groups separated
        # by `;` (e.g. "`a.rs:1` (`Foo`); `b.py:2` (`bar`)"). Splitting on `;`
        # keeps a symbol paired with the path it was actually written next to,
        # instead of checking it against every path anywhere in the row.
        for segment in row.split(";"):
            path_matches = PATH_RE.findall(segment)  # list of (path, line_or_"")
            if not path_matches:
                continue

            rel_paths = [p for p, _line in path_matches]
            resolved: dict[str, str] = {}
            for rel_path in rel_paths:
                abs_path = _resolve_repo_path(rel_path)
                if abs_path.is_dir():
                    # A directory reference (e.g. `web/src/wasm/`) -- nothing
                    # to grep a symbol against, but it does need to exist.
                    continue
                if not abs_path.is_file():
                    norm = rel_path.rstrip("/")
                    if rel_path in OPTIONAL_BUILD_PATHS or norm in OPTIONAL_BUILD_PATHS:
                        continue
                    failures.append(
                        f"{md_path}:{line_no}: code reference `{rel_path}` does not "
                        f"exist relative to repo root {REPO_ROOT}\n    row: {row}"
                    )
                    continue
                try:
                    resolved[rel_path] = abs_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError as err:
                    failures.append(
                        f"{md_path}:{line_no}: code reference `{rel_path}` could not "
                        f"be read: {err}\n    row: {row}"
                    )

            if not resolved or skip_symbols:
                continue

            for symbol in _symbol_candidates(segment, [p for p, _l in path_matches]):
                # Accept either the fully-qualified form (`Type::method`,
                # `module.func`) verbatim, or just its trailing identifier -- a
                # qualified name rarely appears literally in the defining file
                # (e.g. `n_lots` is defined inside `impl UnitParticleBank { ... }`,
                # not written out as `UnitParticleBank::n_lots`).
                base = re.split(r"::|\.", symbol)[-1]
                if not any(
                    symbol in contents or base in contents
                    for contents in resolved.values()
                ):
                    cited_files = ", ".join(sorted(resolved))
                    failures.append(
                        f"{md_path}:{line_no}: symbol `{symbol}` named in this row "
                        f"was not found in any of the cited file(s) ({cited_files})\n"
                        f"    row: {row}"
                    )

    return failures


def test_in_the_code_tables_resolve() -> None:
    all_failures: list[str] = []
    for md_path in iter_doc_files():
        all_failures.extend(_check_file(md_path))

    assert not all_failures, (
        "T-150 docs code-reference guard: one or more 'In the code' table rows "
        "cite a path or symbol that doesn't resolve:\n" + "\n".join(all_failures)
    )


def test_arrival_code_refs_do_not_cite_retired_truncated_normal_fields() -> None:
    """S3.6 — docs must not pin retired v1 arrival symbols on arrival.rs citations."""
    failures: list[str] = []
    for rel in _ARRIVAL_DOC_PATHS:
        md_path = REPO_ROOT / rel
        text = md_path.read_text(encoding="utf-8")
        for line_no, row in _table_data_rows(text):
            if "crates/voi_core/src/arrival.rs" not in row:
                continue
            for span in _all_backtick_spans(row):
                if span in _RETIRED_ARRIVAL_SYMBOLS:
                    failures.append(
                        f"{md_path}:{line_no}: retired symbol `{span}` still cited "
                        f"against arrival.rs\n    row: {row}"
                    )
    assert not failures, (
        "T-163 S3.6: re-pin arrival docs to v2 generative symbols:\n"
        + "\n".join(failures)
    )


def test_arrival_parameters_table_cites_v2_generative_symbols() -> None:
    """S3.6 — parameters table must cite v2 generative fields after re-pin."""
    params_md = (REPO_ROOT / "docs/reference/parameters.md").read_text(encoding="utf-8")
    source_text = "\n".join(
        (REPO_ROOT / rel).read_text(encoding="utf-8") for rel in _ARRIVAL_SOURCE_PATHS
    )
    missing_doc = sorted(sym for sym in _V2_ARRIVAL_SYMBOLS if sym not in params_md)
    missing_code = sorted(sym for sym in _V2_ARRIVAL_SYMBOLS if sym not in source_text)
    assert not missing_code, (
        "arrival/shipments sources must define v2 symbols for docs to cite: "
        f"{missing_code}"
    )
    assert not missing_doc, (
        "RED [S3.6]: docs/reference/parameters.md must cite v2 arrival symbols "
        f"(missing {missing_doc}); retire mu_t/sigma_t rows"
    )


def test_path_regex_matches_expected_examples() -> None:
    # Sanity check on the guard's own regex, independent of current doc content.
    row = (
        "| Order quantity (Rust) | $q$ | "
        "`crates/voi_core/src/policy.rs:201` (`damped_sw_order_f_belief`) |"
    )
    matches = PATH_RE.findall(row)
    assert matches == [("crates/voi_core/src/policy.rs", "201")]
    symbols = _symbol_candidates(row, [p for p, _l in matches])
    assert symbols == ["damped_sw_order_f_belief"]
