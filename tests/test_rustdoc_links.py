"""Guard: /api/rust/ links in VitePress docs resolve after docs:build."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
RUSTDOC_ROOT = DOCS_ROOT / "public" / "api" / "rust"
MANIFEST_PATH = DOCS_ROOT / ".vitepress" / "rustdoc-manifest.json"

LINK_RE = re.compile(r"\[`([^`]+)`\]\((/api/rust/[^)]+)\)")


def _iter_doc_files() -> list[Path]:
    skip = {".vitepress", "node_modules", "public"}
    out: list[Path] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        if any(part in skip for part in path.parts):
            continue
        out.append(path)
    return out


def test_rustdoc_bundle_exists() -> None:
    index = RUSTDOC_ROOT / "voi_core" / "index.html"
    assert index.is_file(), (
        f"Missing {index}; run `cd docs && npm run docs:build` before this test"
    )


def test_rustdoc_links_in_docs_resolve() -> None:
    if not (RUSTDOC_ROOT / "voi_core" / "index.html").is_file():
        pytest.skip("rustdoc bundle not built")

    failures: list[str] = []
    for md in _iter_doc_files():
        for m in LINK_RE.finditer(md.read_text(encoding="utf-8")):
            symbol, url = m.group(1), m.group(2)
            rel = url.removeprefix("/api/rust/").split("#", 1)[0]
            target = RUSTDOC_ROOT / rel
            if not target.is_file():
                failures.append(
                    f"{md}: link for `{symbol}` -> {url} missing at {target}"
                )
    assert not failures, "Broken rustdoc links:\n" + "\n".join(failures)


def test_manifest_linkable_paths_exist_after_build() -> None:
    if not (RUSTDOC_ROOT / "voi_core" / "index.html").is_file():
        pytest.skip("rustdoc bundle not built")

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    for entry in data["entries"]:
        if not entry.get("linkable"):
            continue
        target = RUSTDOC_ROOT / entry["rustdoc_path"].split("#", 1)[0]
        if not target.is_file():
            failures.append(
                f"{entry['symbol']}: expected {target} (manifest rustdoc_path)"
            )
    assert not failures, "Manifest paths missing from rustdoc output:\n" + "\n".join(
        failures
    )
