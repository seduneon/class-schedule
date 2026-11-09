"""A10 — Top-k course preference."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scheduler.config import Config, Mode
from scheduler.domain import CoursePreference, Instance, PreAssignment, SectionType, Solution
from scheduler.preferences import top_k_distance
from scheduler.reporting.excel import write_excel_report
from scheduler.validation import validate
from tests.factory import ablation_a, asg, fast_config, instance, offering, prof


def _cfg(max_rank: int) -> Config:
    return Config.model_validate({"constraints": {"A10": {"mode": "soft", "max_rank": max_rank}}})


def _inst(**kw: object) -> Instance:
    return instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M1"), offering("M2"), offering("M3")],
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("P", "M2", 2),
            CoursePreference("P", "M3", 3),
            CoursePreference("Q", "M1", None),
        ],
        **kw,
    )


def test_a10_top_k_passes() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L")))
    assert validate(inst, sol, _cfg(2), ids=["A10"]) == []


def test_a10_rank_cannot_and_unranked_are_violations() -> None:
    inst = _inst()
    sol = Solution(
        (asg(inst, "P", "M3", "1L"), asg(inst, "Q", "M1", "1L"), asg(inst, "Q", "M2", "1L"))
    )
    msgs = sorted(v.message for v in validate(inst, sol, _cfg(2), ids=["A10"]))
    assert msgs == [
        "P teaches M3 L: rank 3 is outside the top 2",
        "Q teaches M1 L: marked cannot teach, outside the top 2",
        "Q teaches M2 L: unranked, outside the top 2",
    ]
    assert validate(inst, sol, _cfg(3), ids=["A10"])[0].message.startswith("Q teaches M1")


def test_a10_pre_assignment_exempts() -> None:
    inst = _inst(pre_assignments=[PreAssignment("P", "M3", SectionType.L, 1)])
    assert validate(inst, Solution((asg(inst, "P", "M3", "1L"),)), _cfg(1), ids=["A10"]) == []


def _binding() -> Instance:
    """Q (priority 2) gains more from M1 than P loses by taking M2, ranked 3rd (outside the
    top 2). Without A10, Stage A gives Q M1 and P M2; with it, P keeps M1."""
    return instance(
        professors=[prof("P", 1, 1), prof("Q", 1, 1, priority=2.0), prof("R", 1, 1)],
        offerings=[offering("M1"), offering("M2"), offering("X")],
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("P", "X", 2),
            CoursePreference("P", "M2", 3),
            CoursePreference("Q", "M1", 1),
            CoursePreference("Q", "M2", 2),
            CoursePreference("R", "X", 1),
        ],
    )


@pytest.mark.parametrize("on_mode", ["soft", "hard"])
def test_a10_ablation_pair(on_mode: str) -> None:
    cfg = fast_config(constraints={"A10": {"mode": "soft", "max_rank": 2}})
    off, on = ablation_a(_binding(), "A10", on_mode=on_mode, cfg=cfg)
    assert off == ["P teaches M2 L: rank 3 is outside the top 2"]
    assert on == []


def _nobody_in_top_k() -> Instance:
    """M1 has a free taker only outside the top 2; M2 is P's rank 1; M3 needs P too (full)."""
    return instance(
        professors=[prof("P", 1, 1), prof("Q", 0, 3)],
        offerings=[offering("M1"), offering("M2"), offering("M3", n=2, cap=40)],
        course_preferences=[
            CoursePreference("P", "M2", 1),
            CoursePreference("P", "M3", 2),
            CoursePreference("Q", "Z1", 1),
            CoursePreference("Q", "Z2", 2),
            CoursePreference("Q", "M1", 3),
            CoursePreference("Q", "M3", 4),
        ],
    )


def test_a10_is_hard_by_default() -> None:
    assert Config().mode("A10") is Mode.HARD


def test_a10_hard_leaves_section_unassigned_and_report_names_it(tmp_path: Path) -> None:
    """D8: better unassigned than outside the top K."""
    from scheduler.pipeline import run_stage_a

    inst = _nobody_in_top_k()
    cfg = fast_config(constraints={"A10": {"mode": "hard", "max_rank": 2}})
    result = run_stage_a(inst, cfg, presolve=False)
    assert result.solution is not None
    assert validate(inst, result.solution, cfg, ids=["A10"]) == []
    assert sorted(a.course_id for a in result.solution.assignments) == ["M2"]

    path = write_excel_report(tmp_path / "report.xlsx", inst, result.solution, cfg)
    sheet = pd.read_excel(path, sheet_name="unassigned_sections")
    got = [(r.course_id, r.section_label, r.reason) for r in sheet.itertuples()]
    assert got == [
        ("M1", "1L", "no professor has it in their top 2"),
        ("M3", "1L", "eligible professors all at max load: P (1/1)"),
        ("M3", "2L", "eligible professors all at max load: P (1/1)"),
    ]
    assert list(sheet["title"]) == ["M1", "M3", "M3"]
    assert list(sheet["capacity"]) == [30, 40, 40]


def test_a10_report_sheet_is_empty_when_all_assigned(tmp_path: Path) -> None:
    inst = _inst()
    sol = Solution(
        (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"), asg(inst, "P", "M3", "1L"))
    )
    path = write_excel_report(tmp_path / "report.xlsx", inst, sol, _cfg(5))
    sheet = pd.read_excel(path, sheet_name="unassigned_sections")
    assert sheet.empty and "reason" in sheet.columns


def test_a10_distance_past_k() -> None:
    assert top_k_distance(3, 5, 33) == 0.0
    assert top_k_distance(6, 5, 33) == pytest.approx(1 / 28)
    assert top_k_distance(33, 5, 33) == 1.0
    assert top_k_distance(None, 5, 33) == 1.0  # cannot or unranked


def test_a10_two_near_beat_one_far() -> None:
    """K = 1. Either P takes M1 and Q takes M2, ranked 20th of 20 (one section, distance 1),
    or Q takes M1 and both P and R go one rank past K (two sections, distance 1/9 each).
    A count would pick the first; the distance picks the second."""
    inst = instance(
        professors=[prof("P", 1, 1), prof("Q", 1, 1), prof("R", 1, 1)],
        offerings=[offering("M1"), offering("M2"), offering("M3")],
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("P", "M3", 2),
            CoursePreference("P", "Z", 10),  # not offered; only raises m_P to 10
            CoursePreference("Q", "M1", 1),
            CoursePreference("Q", "M2", 20),
            CoursePreference("R", "M3", 1),
            CoursePreference("R", "M2", 2),
            CoursePreference("R", "Z", 10),
        ],
    )
    from scheduler.pipeline import run_stage_a

    cfg = fast_config(constraints={"A10": {"mode": "soft", "max_rank": 1}})
    result = run_stage_a(inst, cfg, presolve=False)
    assert result.solution is not None
    got = sorted((a.professor_id, a.course_id) for a in result.solution.assignments)
    assert got == [("P", "M3"), ("Q", "M1"), ("R", "M2")]
