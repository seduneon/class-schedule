"""Spec ↔ code ↔ test sync (SPEC §4, §12)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import scheduler.model.stage_a.build
import scheduler.model.stage_b.build  # noqa: F401
from scheduler.config import CONSTRAINT_INDEX
from scheduler.model.registry import BUILDERS
from scheduler.validation import CHECKS

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(
    r"^\|\s*(?P<id>[AB]\d+)\s*\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<stage>[AB])\s*\|"
    r"\s*(?P<priority>\w+)\s*\|\s*(?P<default>[\w*]+)\s*\|\s*(?P<status>\w+)\s*\|$"
)


def spec_rows() -> dict[str, dict[str, str]]:
    text = (ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")
    section = text.split("## 4. Constraint index", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        m = ROW.match(line.strip())
        if m:
            rows[m["id"]] = m.groupdict()
    return rows


def _test_file_for(cid: str) -> Path | None:
    stem = f"{cid[0].lower()}{int(cid[1:]):02d}"
    for path in sorted((ROOT / "tests").rglob(f"test_{stem}_*.py")):
        if cid in path.read_text(encoding="utf-8"):
            return path
    return None


def test_spec_table_matches_constraint_index() -> None:
    rows = spec_rows()
    assert set(rows) == {c.id for c in CONSTRAINT_INDEX}
    for spec in CONSTRAINT_INDEX:
        row = rows[spec.id]
        assert row["stage"] == spec.stage.value
        assert row["priority"] == spec.priority
        assert row["default"].rstrip("*") == spec.default_mode.value
        assert row["status"] in ("planned", "implemented")


def test_registered_ids_appear_in_spec() -> None:
    rows = spec_rows()
    assert set(BUILDERS) <= set(rows)
    assert set(CHECKS) <= set(rows)


def test_implemented_rows_are_complete() -> None:
    config = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
    for cid, row in spec_rows().items():
        if row["status"] != "implemented":
            continue
        assert cid in BUILDERS, f"{cid}: no builder"
        assert cid in CHECKS, f"{cid}: no validator check"
        assert cid in config["constraints"], f"{cid}: no entry in configs/default.yaml"
        assert _test_file_for(cid) is not None, f"{cid}: no test file mentioning it"


def test_default_yaml_modes_match_spec() -> None:
    config = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
    for cid, row in spec_rows().items():
        mode = config["constraints"][cid]["mode"]
        mode = "off" if mode is False else mode
        assert mode == row["default"].rstrip("*"), cid
