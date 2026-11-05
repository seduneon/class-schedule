"""Repository layout (SPEC §10): tracked files stay inside the documented tree."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# SPEC §10: the only entries allowed at the repository root.
ALLOWED_ROOT = {
    ".github",
    ".gitignore",
    "CLAUDE.md",
    "README.md",
    "configs",
    "data",
    "docs",
    "experiments",
    "pyproject.toml",
    "src",
    "tests",
    "uv.lock",
}
ALLOWED_DATA = {"examples"}
# Real data arrives as Excel, archives or PDFs; none of these belong in git.
REAL_DATA_SUFFIXES = {".xlsx", ".xls", ".zip", ".pdf"}


def _tracked() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted(out.stdout.splitlines())


def test_tracked_files_stay_in_the_spec_tree() -> None:
    stray = [p for p in _tracked() if p.split("/")[0] not in ALLOWED_ROOT]
    assert stray == [], f"outside the SPEC §10 tree: {stray}"


def test_only_examples_are_tracked_under_data() -> None:
    parts = [p.split("/") for p in _tracked() if p.startswith("data/")]
    stray = ["/".join(p) for p in parts if len(p) < 3 or p[1] not in ALLOWED_DATA]
    assert stray == [], f"data/ may only track data/examples/: {stray}"


def test_no_real_data_files_are_tracked() -> None:
    found = [p for p in _tracked() if Path(p).suffix.lower() in REAL_DATA_SUFFIXES]
    assert found == [], f"real-data file types are never committed: {found}"
