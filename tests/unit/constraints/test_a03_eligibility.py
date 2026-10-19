"""A3 — Eligibility."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import CoursePreference, Instance, PreAssignment, SectionType, Solution
from scheduler.validation import validate
from tests.factory import asg, instance, offering, prof


def _inst(**kw: object) -> Instance:
    return instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M101"), offering("M102")],
        course_preferences=[
            CoursePreference("P", "M101", 1),
            CoursePreference("Q", "M101", None),
        ],
        **kw,
    )


def test_a3_ranked_course_passes() -> None:
    inst = _inst()
    assert validate(inst, Solution((asg(inst, "P", "M101", "1L"),)), Config(), ids=["A3"]) == []


def test_a3_cannot_and_unranked_are_violations() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "Q", "M101", "1L"), asg(inst, "P", "M102", "1L")))
    msgs = sorted(v.message for v in validate(inst, sol, Config(), ids=["A3"]))
    assert msgs == [
        "P teaches M102 L: unranked (unranked_policy = forbid)",
        "Q teaches M101 L: marked cannot teach",
    ]
    allow = Config.model_validate({"preferences": {"unranked_policy": "allow_low"}})
    assert len(validate(inst, sol, allow, ids=["A3"])) == 1


def test_a3_pre_assignment_overrides() -> None:
    inst = _inst(pre_assignments=[PreAssignment("Q", "M101", SectionType.L, 1)])
    assert validate(inst, Solution((asg(inst, "Q", "M101", "1L"),)), Config(), ids=["A3"]) == []


def test_a3_ablation_pair() -> None:
    from tests.factory import ablation_a

    inst = instance(
        professors=[prof("P", 0, 2)],
        offerings=[offering("M101"), offering("M102")],
        course_preferences=[CoursePreference("P", "M101", None), CoursePreference("P", "M102", 1)],
    )
    off, on = ablation_a(inst, "A3")
    assert off == ["P teaches M101 L: marked cannot teach"]
    assert on == []


def _typed() -> Instance:
    """P ranks the M101 lecture but cannot take its recitation (SPEC §3.4 typed ranks)."""
    return instance(
        professors=[prof("P", 0, 2)],
        offerings=[offering("M101"), offering("M101", kind="R")],
        course_preferences=[
            CoursePreference("P", "M101", 1),
            CoursePreference("P", "M101", None, SectionType.R),
        ],
    )


def test_a3_typed_rank_overrides_course_rank() -> None:
    inst = _typed()
    assert inst.course_type_rank[("P", "M101", SectionType.L)] == 1
    assert inst.course_type_rank[("P", "M101", SectionType.R)] is None
    sol = Solution((asg(inst, "P", "M101", "1L"), asg(inst, "P", "M101", "1R")))
    msgs = [v.message for v in validate(inst, sol, Config(), ids=["A3"])]
    assert msgs == ["P teaches M101 R: marked cannot teach"]


def test_a3_typed_ablation_pair() -> None:
    from tests.factory import ablation_a

    off, on = ablation_a(_typed(), "A3")
    assert off == ["P teaches M101 R: marked cannot teach"]
    assert on == []
