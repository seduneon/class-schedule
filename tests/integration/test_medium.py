"""Medium example: the anonymized Fall 2026 instance (SPEC §8.1, D5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scheduler.config import Config
from scheduler.diagnostics import presolve_checks
from scheduler.domain import Instance, SectionType
from scheduler.io import read_instance
from scheduler.pipeline import run_stage_a, run_stage_b

MEDIUM = Path(__file__).resolve().parents[2] / "data" / "examples" / "medium"


@pytest.fixture(scope="module")
def medium() -> Instance:
    return read_instance(MEDIUM)


def test_medium_reads(medium: Instance) -> None:
    assert len(medium.professors) == 26
    assert len(medium.sections) == 74
    assert medium.offering_info[("MATH162", SectionType.R)].num_sections == 15
    assert medium.room_patterns  # room availability from time_room.xlsx


def test_medium_room_slot_shortage_is_reported(medium: Instance) -> None:
    """74 sections, 66 (room, pattern) slots: L1 must say so before solving."""
    codes = {(f.severity, f.code) for f in presolve_checks(medium, Config())}
    assert ("error", "room_slots") in codes


@pytest.mark.slow
def test_medium_full_pipeline(medium: Instance) -> None:
    cfg = Config().with_updates(solver={"time_limit_s": 600})
    a = run_stage_a(medium, cfg, presolve=False)
    assert a.solution is not None
    b = run_stage_b(medium, cfg, a.solution.assignments, presolve=False)
    assert b.solution is not None and b.solution.placements is not None
    hard = [v for v in b.violations if v.severity == "error" and v.id not in ("A1", "B1")]
    assert hard == []
    assert len(b.solution.placements) <= 66
