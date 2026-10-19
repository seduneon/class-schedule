"""Architecture rules (SPEC §10, §12)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "scheduler"


def _loaded_after_import(module: str) -> set[str]:
    code = f"import sys, {module}; print(','.join(sorted(sys.modules)))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return set(out.stdout.strip().split(","))


def _static_imports(package: Path) -> set[str]:
    names: set[str] = set()
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def test_validation_never_imports_pulp() -> None:
    assert "pulp" not in _static_imports(SRC / "validation")
    assert "pulp" not in _loaded_after_import("scheduler.validation")


@pytest.mark.parametrize(
    "module",
    ["scheduler.model.stage_a.build", "scheduler.model.stage_b.build", "scheduler.model.context"],
)
def test_model_never_imports_pandas(module: str) -> None:
    assert "pandas" not in _static_imports(SRC / "model")
    assert "pandas" not in _loaded_after_import(module)


def test_model_never_reads_files() -> None:
    for path in (SRC / "model").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", f"{path} calls open()"
            if isinstance(node, ast.Attribute):
                assert node.attr not in ("read_text", "read_csv", "read_excel"), (
                    f"{path} reads files"
                )


def test_pandas_only_in_io_and_reporting() -> None:
    allowed = {"io", "reporting"}
    for sub in SRC.iterdir():
        if sub.is_dir() and sub.name not in allowed and sub.name != "__pycache__":
            assert "pandas" not in _static_imports(sub), f"{sub.name} imports pandas"
