"""Guard: zero legacy particle-filter acronym references in the repo."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Build at runtime so this file does not embed the banned token.
_BANNED = "r" + "bpf"
_SCAN_ROOTS = (
    "src",
    "tests",
    "crates",
    "scripts",
    "packaging",
    "web/src",
    ".team",
)
_TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".rs",
        ".md",
        ".yml",
        ".yaml",
        ".toml",
        ".json",
        ".ts",
        ".tsx",
        ".js",
        ".sh",
    }
)


def _find_banned_paths(root: Path, banned: str) -> list[str]:
    """Pure-Python scan of source trees (CI has no ripgrep)."""
    banned_lower = banned.lower()
    hits: list[str] = []
    for rel in _SCAN_ROOTS:
        base = root / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix and path.suffix not in _TEXT_SUFFIXES:
                continue
            try:
                blob = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in blob:
                continue
            text = blob.decode("utf-8", errors="ignore")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if banned_lower in line.lower():
                    hits.append(f"{path.relative_to(root)}:{line_no}:{line.strip()}")
                    break
    return hits


def test_no_legacy_particle_filter_acronym() -> None:
    hits = _find_banned_paths(_REPO_ROOT, _BANNED)
    assert not hits, (
        "legacy particle-filter acronym must not appear anywhere in the repo; "
        "found:\n" + "\n".join(hits)
    )
