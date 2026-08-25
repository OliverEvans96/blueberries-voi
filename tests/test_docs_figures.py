"""Guard: docs figure references must exist and no 'coming soon' placeholders."""

from __future__ import annotations

import re

import pytest

from _docs_helpers import DOCS_ROOT, iter_doc_files

pytestmark = pytest.mark.docs

FIGURES_PUBLIC = DOCS_ROOT / "public" / "figures"
FIGURE_REF_RE = re.compile(r"!\[[^\]]*\]\(/figures/([^)]+)\)")
COMING_SOON_RE = re.compile(r"Figure \(coming soon\)", re.IGNORECASE)


def test_no_figure_coming_soon_placeholders() -> None:
    offenders: list[str] = []
    for path in iter_doc_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if COMING_SOON_RE.search(line):
                offenders.append(
                    f"{path.relative_to(DOCS_ROOT)}:{line_no}: {line.strip()}"
                )
    assert not offenders, "Figure (coming soon) placeholders remain:\n" + "\n".join(
        offenders
    )


def test_figure_png_references_exist() -> None:
    missing: list[str] = []
    for path in iter_doc_files():
        text = path.read_text(encoding="utf-8")
        for match in FIGURE_REF_RE.finditer(text):
            name = match.group(1)
            if not name.endswith(".png"):
                continue
            target = FIGURES_PUBLIC / name
            if not target.is_file():
                missing.append(f"{path.relative_to(DOCS_ROOT)} → /figures/{name}")
    assert not missing, "Missing figure files:\n" + "\n".join(sorted(missing))
