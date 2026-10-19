"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import CoursePreference, Instance, Solution, Unavailability
from scheduler.validation import validate
from tests.factory import ablation_a, asg, instance, offering, prof


def _inst() -> Instance:
    return instance(
        professors=[prof("P", 0, 3), prof("Q", 0, 10)],
        offerings=[offering("M1", n=2)],
        unavailability=[Unavailability("P", "Tue", 0, 24 * 60)],  # P can only use MWF0900
        course_preferences=[CoursePreference("P", "M1", 1), CoursePreference("Q", "M1", 2)],
    )


def test_a8_validator() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M1", "2L")))
    assert [v.message for v in validate(inst, sol, Config(), ids=["A8"])] == [
        "P has 2 sections but only 1 non-overlapping available time patterns"
    ]


def test_a8_ablation_pair() -> None:
    off, on = ablation_a(_inst(), "A8")
    assert len(off) == 1 and on == []
