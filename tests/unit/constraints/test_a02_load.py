"""A2 — Teaching load range."""

from __future__ import annotations

from scheduler.config import Config, Mode
from scheduler.domain import Instance, Solution
from scheduler.validation import validate
from tests.factory import asg, tiny_assignments


def test_a2_within_range_passes(tiny: Instance) -> None:
    assert validate(tiny, Solution(tiny_assignments(tiny)), Config(), ids=["A2"]) == []


def test_a2_underload_is_soft_warning(tiny: Instance) -> None:
    sol = Solution(tiny_assignments(tiny)[:3])  # C teaches nothing
    vs = validate(tiny, sol, Config(), ids=["A2"])
    assert [(v.severity, v.entities, v.size) for v in vs] == [("warning", ("C",), 1.0)]
    hard = Config().with_mode("A2", Mode.HARD)
    assert validate(tiny, sol, hard, ids=["A2"])[0].severity == "error"


def test_a2_overload_is_error_unless_allowed(tiny: Instance) -> None:
    sol = Solution((*tiny_assignments(tiny)[:3], asg(tiny, "A", "MATH361", "1L")))
    vs = [v for v in validate(tiny, sol, Config(), ids=["A2"]) if v.entities == ("A",)]
    assert len(vs) == 1 and vs[0].severity == "error" and "above the maximum" in vs[0].message
    allow = Config.model_validate({"constraints": {"A2": {"mode": "soft", "allow_overload": True}}})
    vs = [v for v in validate(tiny, sol, allow, ids=["A2"]) if v.entities == ("A",)]
    assert vs[0].severity == "warning"


def test_a2_ablation_pair() -> None:
    from scheduler.domain import CoursePreference
    from tests.factory import ablation_a, instance, offering, prof

    inst = instance(
        professors=[prof("P", 1, 1), prof("Q", 1, 3)],
        offerings=[offering("M101"), offering("M102"), offering("M103")],
        course_preferences=[
            CoursePreference("P", "M101", 1),
            CoursePreference("P", "M102", 2),
            CoursePreference("Q", "M103", 1),
        ],
    )
    off, on = ablation_a(inst, "A2", on_mode="soft")
    assert off == ["P teaches 2 units, above the maximum 1"]
    assert on == []
