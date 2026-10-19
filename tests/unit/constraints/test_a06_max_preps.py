"""A6 — Max distinct preparations."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import CoursePreference, Instance, Solution
from scheduler.validation import validate
from tests.factory import ablation_a, asg, instance, offering, prof


def _inst() -> Instance:
    return instance(
        professors=[prof("P", 0, 2, max_preps=1), prof("Q", 0, 1)],
        offerings=[offering("M1"), offering("M2", n=2)],
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("P", "M2", 2),
            CoursePreference("Q", "M2", 1),
            CoursePreference("Q", "M1", 2),
        ],
    )


def test_a6_validator() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L")))
    assert [v.size for v in validate(inst, sol, Config(), ids=["A6"])] == [1]
    ok = Solution((asg(inst, "P", "M2", "1L"), asg(inst, "P", "M2", "2L")))
    assert validate(inst, ok, Config(), ids=["A6"]) == []


def test_a6_ablation_pair() -> None:
    off, on = ablation_a(_inst(), "A6")
    assert off == ["P teaches 2 distinct courses (M1, M2), more than 1"]
    assert on == []
