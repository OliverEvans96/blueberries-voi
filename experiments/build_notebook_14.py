#!/usr/bin/env python3
"""Build ``notebooks/14_lgtin_vs_upc_filter_accuracy.ipynb`` from its markdown source.

Cell text lives in ``experiments/notebook_14_source.md`` rather than in string
literals here, so prose wraps where prose should wrap.

Usage::

    uv run python experiments/build_notebook_14.py
    cd notebooks && uv run jupyter nbconvert --to notebook --execute --inplace \
        14_lgtin_vs_upc_filter_accuracy.ipynb
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "experiments" / "notebook_14_source.md"
OUT = ROOT / "notebooks" / "14_lgtin_vs_upc_filter_accuracy.ipynb"

MARKDOWN_MARKER = "<!-- markdown -->"
CODE_MARKER = "<!-- code -->"


def parse_cells(text: str) -> list[nbf.NotebookNode]:
    """Split the source on cell markers, ignoring anything before the first one."""
    cells: list[nbf.NotebookNode] = []
    kind: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if kind is None:
            return
        body = "\n".join(buf).strip("\n")
        if not body:
            return
        cells.append(
            nbf.v4.new_markdown_cell(body)
            if kind == "markdown"
            else nbf.v4.new_code_cell(body)
        )

    for line in text.splitlines():
        stripped = line.strip()
        if stripped in (MARKDOWN_MARKER, CODE_MARKER):
            flush()
            kind = "markdown" if stripped == MARKDOWN_MARKER else "code"
            buf = []
            continue
        buf.append(line)
    flush()
    return cells


def main() -> None:
    cells = parse_cells(SRC.read_text())
    if not cells:
        msg = f"no cells parsed from {SRC}"
        raise SystemExit(msg)
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python", "version": "3.11"}
    OUT.write_text(nbf.writes(nb) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
