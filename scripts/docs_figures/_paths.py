"""Repository and output paths for doc figure scripts."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "public" / "figures"
