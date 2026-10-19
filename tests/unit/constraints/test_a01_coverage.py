"""A1 — Section coverage."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution
from scheduler.validation import validate
from tests.factory import asg, tiny_assignments


def _a1(inst: Instance, sol: Solution) -> list[str]:
    return [v.message for v in validate(inst, sol, Config(), ids=["A1"])]


def test_a1_full_coverage_passes(tiny: Instance) -> None:
    assert _a1(tiny, Solution(tiny_assignments(tiny))) == []


def test_a1_uncovered_section_is_reported(tiny: Instance) -> None:
    sol = Solution(tiny_assignments(tiny)[1:])
    vs = validate(tiny, sol, Config(), ids=["A1"])
    assert len(vs) == 1 and vs[0].severity == "error" and vs[0].size == 1
    assert "MATH161 L: 1 of 2 section(s) uncovered" in vs[0].message


def test_a1_duplicate_and_unknown_labels(tiny: Instance) -> None:
    dup = asg(tiny, "B", "MATH161", "1L")
    sol = Solution((*tiny_assignments(tiny), dup))
    assert any("assigned 2 times" in m for m in _a1(tiny, sol))
    bogus = dup.__class__("B", "MATH161", dup.section_type, "9L", 40, 1.0)
    assert any(
        "no such section" in m for m in _a1(tiny, Solution((*tiny_assignments(tiny), bogus)))
    )


def test_a1_ablation_pair() -> None:
    from scheduler.domain import CoursePreference
    from tests.factory import ablation_a, instance, offering, prof

    inst = instance(
        professors=[prof("P", 0, 1), prof("Q", 0, 1)],
        offerings=[offering("M101"), offering("M102")],
        course_preferences=[
            CoursePreference("P", "M101", 1),
            CoursePreference("P", "M102", 2),
            CoursePreference("Q", "M101", 1),
            CoursePreference("Q", "M102", 2),
        ],
    )
    off, on = ablation_a(inst, "A1")
    assert off and on == []
