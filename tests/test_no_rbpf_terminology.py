"""Guard: zero legacy particle-filter acronym references in the repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Build at runtime so this file does not embed the banned token.
_BANNED = "r" + "bpf"


def test_no_legacy_particle_filter_acronym() -> None:
    result = subprocess.run(
        [
            "rg",
            "-i",
            _BANNED,
            ".",
            "--glob",
            "!notebooks/**",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, (
        "legacy particle-filter acronym must not appear anywhere in the repo; "
        f"found:\n{result.stdout}"
    )
