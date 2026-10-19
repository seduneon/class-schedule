"""A7 — Lecture–recitation staffing."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.derived import recitation_band
from scheduler.domain import CoursePreference, Instance, SectionType, Solution
from scheduler.pipeline import run_stage_a
from scheduler.validation import validate
from tests.factory import ablation_a, asg, fast_config, instance, offering, prof


def _inst() -> Instance:
    return instance(
        professors=[prof("P", 0, 3), prof("Q", 0, 2)],
        offerings=[offering("C1", n=2), offering("C1", n=2, kind="R")],
        course_preferences=[CoursePreference("P", "C1", 1), CoursePreference("Q", "C1", 1)],
    )


def _cfg(staffing: str) -> Config:
    return fast_config(recitations={"staffing": staffing}).with_mode("A7", "hard")


def test_recitation_band() -> None:
    assert recitation_band(1, 2, 3) == (1, 2)
    assert recitation_band(2, 2, 3) == (3, 3)
    assert recitation_band(0, 2, 3) == (0, 0)


def test_a7_same_as_lecture_validator() -> None:
    inst = _inst()
    bad = Solution(
        (
            asg(inst, "P", "C1", "1L"),
            asg(inst, "Q", "C1", "2L"),
            asg(inst, "Q", "C1", "1R"),
            asg(inst, "Q", "C1", "2R"),
        )
    )
    msgs = [v.message for v in validate(inst, bad, _cfg("same_as_lecture"), ids=["A7"])]
    assert msgs == [
        "P teaches 1 of 2 C1 lectures and should take 1-1 of 2 recitations, but takes 0",
        "Q teaches 1 of 2 C1 lectures and should take 1-1 of 2 recitations, but takes 2",
    ]


def test_a7_ablation_pair_same_as_lecture() -> None:
    off, on = ablation_a(
        _inst(), "A7", cfg=fast_config(recitations={"staffing": "same_as_lecture"})
    )
    assert off and on == []


def test_a7_external_sends_recitations_to_placeholders() -> None:
    result = run_stage_a(_inst(), _cfg("external"), presolve=False)
    assert result.solution is not None
    rec = [a for a in result.solution.assignments if a.section_type is SectionType.R]
    assert {a.professor_id for a in rec} == {"TBA-C1"} and len(rec) == 2
    assert [v for v in result.violations if v.id in ("A1", "A7")] == []
