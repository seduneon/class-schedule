"""B3 — No professor overlap."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution
from scheduler.validation import validate
from tests.factory import asg, instance, offering, pattern, plc, prof, room


def test_b3_valid_solution_passes(tiny: Instance) -> None:
    from tests.factory import tiny_solution

    assert validate(tiny, tiny_solution(tiny), Config(), ids=["B3"]) == []


def test_b3_overlap_detected_by_time_not_label() -> None:
    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M101"), offering("M102")],
        rooms=[room("R1"), room("R2")],
        patterns=[
            pattern("MWF0900", "MWF", "09:00", "09:50"),
            pattern("W0930", "W", "09:30", "10:45"),
        ],
    )
    sol = Solution(
        (asg(inst, "P", "M101", "1L"), asg(inst, "P", "M102", "1L")),
        (plc("M101", "1L", "MWF0900", "R1"), plc("M102", "1L", "W0930", "R2")),
    )
    vs = validate(inst, sol, Config(), ids=["B3"])
    assert [v.entities for v in vs] == [("P", "M101-1L", "M102-1L")]


def test_b3_placeholders_are_exempt() -> None:
    inst = instance(
        professors=[],
        offerings=[offering("M101", kind="R", n=2)],
        rooms=[room("R1"), room("R2")],
    )
    sol = Solution(
        (asg(inst, "TBA-M101", "M101", "1R"), asg(inst, "TBA-M101", "M101", "2R")),
        (plc("M101", "1R", "MWF0900", "R1"), plc("M101", "2R", "MWF0900", "R2")),
    )
    assert validate(inst, sol, Config(), ids=["B3"]) == []


def test_b3_ablation_pair() -> None:
    from tests.factory import ablation_b, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P")],
        offerings=[offering("M101"), offering("M102")],
        rooms=[room("R1"), room("R2")],
    )
    sections = (asg(inst, "P", "M101", "1L"), asg(inst, "P", "M102", "1L"))
    off, on = ablation_b(inst, sections, "B3")
    assert len(off) == 1 and "at the same time" in off[0]
    assert on == []
