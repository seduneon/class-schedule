"""A5 — Multi-section preference."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import CoursePreference, Instance, Solution
from scheduler.pipeline import run_stage_a
from scheduler.validation import validate
from tests.factory import ablation_a, asg, fast_config, instance, offering, prof


def _inst(mu: int) -> Instance:
    return instance(
        professors=[prof("P", 0, 2, multi_section_pref=mu), prof("Q", 0, 2)],
        offerings=[offering("M1", n=2), offering("M2", n=2)],
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("P", "M2", 2),
            CoursePreference("Q", "M2", 1),
            CoursePreference("Q", "M1", 2),
        ],
    )


def test_a5_validator() -> None:
    inst = _inst(-1)
    two = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M1", "2L")))
    vs = validate(inst, two, Config(), ids=["A5"])
    assert [(v.severity, v.size) for v in vs] == [("warning", 1)]
    one_each = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L")))
    assert validate(inst, one_each, Config(), ids=["A5"]) == []
    liker = _inst(1)
    assert validate(liker, two, Config(), ids=["A5"]) == []


def test_a5_ablation_pair() -> None:
    off, on = ablation_a(_inst(-1), "A5")
    assert off == ["P prefers one section per course but teaches 2 of M1"]
    assert on == []


def test_a5_bonus_for_multi_section_lovers() -> None:
    # Q (mu = +1) is indifferent between one or two M1 sections by weight alone;
    # the bonus breaks the tie toward two sections of the same course.
    inst = instance(
        professors=[prof("Q", 2, 2, multi_section_pref=1)],
        offerings=[offering("M1", n=2), offering("M2", n=1)],
        course_preferences=[CoursePreference("Q", "M1", 1), CoursePreference("Q", "M2", 1)],
    )
    result = run_stage_a(inst, fast_config(), presolve=False)
    assert result.solution is not None
    assert sorted(a.course_id for a in result.solution.assignments) == ["M1", "M1"]
