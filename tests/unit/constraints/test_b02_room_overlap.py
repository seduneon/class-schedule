"""B2 — No room overlap."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance
from scheduler.validation import validate
from tests.factory import plc, tiny_solution, with_placements


def test_b2_valid_solution_passes(tiny: Instance) -> None:
    assert validate(tiny, tiny_solution(tiny), Config(), ids=["B2"]) == []


def test_room_cannot_be_double_booked(tiny: Instance) -> None:
    """Regression: two sections in one room at the same time."""
    sol = with_placements(tiny_solution(tiny), plc("MATH351", "1L", "TR0900", "7.101"))
    vs = validate(tiny, sol, Config(), ids=["B2"])
    assert len(vs) == 1 and vs[0].severity == "error"
    assert vs[0].entities == ("7.101", "MATH351-1L", "MATH361-1L")


def test_b2_ablation_pair() -> None:
    from tests.factory import ablation_b, asg, offering, prof, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P"), prof("Q")], offerings=[offering("M101"), offering("M102")]
    )
    sections = (asg(inst, "P", "M101", "1L"), asg(inst, "Q", "M102", "1L"))
    off, on = ablation_b(inst, sections, "B2")
    assert len(off) == 1 and "double-booked" in off[0]
    assert on == []


def test_solver_never_double_books_rooms() -> None:
    """Regression: the solved timetable has no room clash even when everyone wants 9am."""
    from scheduler.pipeline import run_stage_b
    from tests.factory import asg, fast_config, offering, prof, room, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P"), prof("Q"), prof("S")],
        offerings=[offering("M101"), offering("M102"), offering("M103")],
        rooms=[room("R1"), room("R2")],
    )
    sections = (
        asg(inst, "P", "M101", "1L"),
        asg(inst, "Q", "M102", "1L"),
        asg(inst, "S", "M103", "1L"),
    )
    result = run_stage_b(inst, fast_config(), sections)
    assert [v for v in result.violations if v.id.startswith("B")] == []
    assert result.objective(1) == 0
