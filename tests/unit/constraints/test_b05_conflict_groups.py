"""B5 — Conflict groups."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import ConflictGroup, Instance, Solution
from scheduler.validation import validate
from tests.factory import asg, instance, offering, plc, prof, room, tiny_solution, with_placements


def test_b5_valid_solution_passes(tiny: Instance) -> None:
    assert validate(tiny, tiny_solution(tiny), Config(), ids=["B5"]) == []


def test_b5_level_group_overlap(tiny: Instance) -> None:
    sol = with_placements(tiny_solution(tiny), plc("MATH351", "1L", "TR0900", "7.102"))
    vs = validate(tiny, sol, Config(), ids=["B5"])
    assert [v.entities for v in vs] == [("level_300", "MATH351-1L", "MATH361-1L")]
    off = Config.model_validate({"conflict_groups": {"auto_levels": False}})
    assert validate(tiny, sol, off, ids=["B5"]) == []


def test_same_course_sections_may_overlap_in_conflict_group() -> None:
    """Regression: sections of the same course are alternatives for students."""
    inst = instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M301", n=2), offering("M302")],
        rooms=[room("R1"), room("R2")],
        conflict_groups=[ConflictGroup("core", frozenset({"M301", "M302"}), "soft", 2.0)],
    )
    sol = Solution(
        (asg(inst, "P", "M301", "1L"), asg(inst, "Q", "M301", "2L"), asg(inst, "P", "M302", "1L")),
        (
            plc("M301", "1L", "MWF0900", "R1"),
            plc("M301", "2L", "MWF0900", "R2"),
            plc("M302", "1L", "TR0900", "R1"),
        ),
    )
    assert validate(inst, sol, Config(), ids=["B5"]) == []
    clash = with_placements(sol, plc("M302", "1L", "MWF0900", "R1"))
    sev = {v.entities[0]: v.severity for v in validate(inst, clash, Config(), ids=["B5"])}
    assert sev == {"core": "warning", "level_300": "error"}


def test_b5_ablation_pair() -> None:
    from tests.factory import ablation_b, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M301"), offering("M302")],
        rooms=[room("R1"), room("R2")],
    )
    sections = (asg(inst, "P", "M301", "1L"), asg(inst, "Q", "M302", "1L"))
    off, on = ablation_b(inst, sections, "B5")
    assert len(off) == 1 and "level_300" in off[0]
    assert on == []


def test_solver_lets_same_course_sections_overlap() -> None:
    """Regression: B5 must not separate sections of the same course."""
    from scheduler.pipeline import run_stage_b
    from tests.factory import fast_config, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M301", n=2)],
        rooms=[room("R1"), room("R2")],
    )
    sections = (asg(inst, "P", "M301", "1L"), asg(inst, "Q", "M301", "2L"))
    result = run_stage_b(inst, fast_config().with_mode("B6", "off"), sections)
    assert result.solution is not None and result.solution.placements is not None
    assert {p.pattern_id for p in result.solution.placements} == {"MWF0900"}
