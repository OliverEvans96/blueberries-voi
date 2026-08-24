"""Guard: manifest symbols in voi_core must have a /// or //! doc comment."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / ".vitepress" / "rustdoc-manifest.json"
VOI_CORE_SRC = REPO_ROOT / "crates" / "voi_core" / "src"


def _has_doc_above(lines: list[str], idx: int) -> bool:
    j = idx - 1
    while j >= 0 and lines[j].strip() == "":
        j -= 1
    if j < 0:
        return False
    return lines[j].lstrip().startswith("///") or lines[j].lstrip().startswith("//!")


def _find_definition(path: Path, symbol: str) -> int | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if "::" in symbol:
        ty, method = symbol.split("::", 1)
        method = method.split("(")[0]
        if method == "default":
            pat = re.compile(rf"^\s*fn\s+{re.escape(method)}\b")
        else:
            pat = re.compile(rf"^\s*pub\s+fn\s+{re.escape(method)}\b")
    else:
        base = symbol.rstrip("()")
        pat = re.compile(
            rf"^\s*(?:pub\s+)?(?:fn|struct|enum|const|type)\s+{re.escape(base)}\b"
        )
        # Fallback: a plain struct/enum field declaration (`pub foo: Type,`), which the
        # item-level pattern above doesn't match but which can carry its own `///` doc
        # comment -- e.g. `ModelParams::demand_mu` is cited by name, not as a `fn`/`struct`.
        field_pat = re.compile(rf"^\s*pub\s+{re.escape(base)}\s*:")
        for i, line in enumerate(lines):
            if pat.search(line):
                return i
        for i, line in enumerate(lines):
            if field_pat.search(line):
                return i
        return None
    for i, line in enumerate(lines):
        if pat.search(line):
            return i
    return None


def test_manifest_symbols_have_doc_comments() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    for entry in data["entries"]:
        module = entry["module"]
        symbol = entry["symbol"]
        path = VOI_CORE_SRC / f"{module}.rs"
        if not path.is_file():
            failures.append(f"{symbol}: missing module file {path}")
            continue
        idx = _find_definition(path, symbol)
        if idx is None:
            failures.append(f"{symbol}: no definition in {path}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if not _has_doc_above(lines, idx):
            failures.append(f"{symbol}: no /// doc comment at {path}:{idx + 1}")
    assert not failures, "Missing rustdoc stubs:\n" + "\n".join(failures)
