"""Guard: zero legacy particle-filter acronym references in the repo."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Build at runtime so this file does not embed the banned token.
_BANNED = "r" + "bpf"
_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".worktrees",
        "notebooks",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
    }
)


def _find_banned_paths(root: Path, banned: str) -> list[str]:
    """Pure-Python repo scan (CI has no ripgrep)."""
    banned_lower = banned.lower()
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if banned_lower in line.lower():
                rel = path.relative_to(root)
                hits.append(f"{rel}:{line_no}:{line.strip()}")
                break
    return hits


def test_no_legacy_particle_filter_acronym() -> None:
    hits = _find_banned_paths(_REPO_ROOT, _BANNED)
    assert not hits, (
        "legacy particle-filter acronym must not appear anywhere in the repo; "
        "found:\n" + "\n".join(hits)
    )
