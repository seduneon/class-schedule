"""A4 — Pre-assignments."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, PreAssignment, SectionType, Solution
from scheduler.validation import validate
from tests.factory import asg, instance, offering, prof


def _inst() -> Instance:
    return instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M101", n=2)],
        pre_assignments=[PreAssignment("P", "M101", SectionType.L, 1, ("2L",))],
    )


def test_a4_satisfied() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "P", "M101", "2L"), asg(inst, "Q", "M101", "1L")))
    assert validate(inst, sol, Config(), ids=["A4"]) == []


def test_a4_missing_count_and_wrong_label() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "Q", "M101", "2L"), asg(inst, "Q", "M101", "1L")))
    msgs = sorted(v.message for v in validate(inst, sol, Config(), ids=["A4"]))
    assert msgs == [
        "M101-2L is pre-assigned to P but assigned to Q",
        "P was pre-assigned 1 M101 L section(s) but has 0",
    ]
    sol = Solution((asg(inst, "P", "M101", "1L"), asg(inst, "Q", "M101", "2L")))
    assert [v.message for v in validate(inst, sol, Config(), ids=["A4"])] == [
        "M101-2L is pre-assigned to P but assigned to Q"
    ]


def test_a4_ablation_pair() -> None:
    from scheduler.domain import CoursePreference
    from tests.factory import ablation_a

    inst = instance(
        professors=[prof("P", 1, 1), prof("Q", 1, 1)],
        offerings=[offering("M101"), offering("M102")],
        course_preferences=[
            CoursePreference("P", "M102", 1),
            CoursePreference("P", "M101", 2),
            CoursePreference("Q", "M101", 1),
            CoursePreference("Q", "M102", 2),
        ],
        pre_assignments=[PreAssignment("P", "M101", SectionType.L, 1)],
    )
    off, on = ablation_a(inst, "A4")
    assert off == ["P was pre-assigned 1 M101 L section(s) but has 0"]
    assert on == []
