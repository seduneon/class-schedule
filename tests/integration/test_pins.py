"""L4 — pins and locks."""

from __future__ import annotations

from dataclasses import replace

from scheduler.diagnostics import presolve_checks
from scheduler.domain import Instance, SectionType, StageAPin, StageBPin
from scheduler.pipeline import run_stage_a, run_stage_b
from tests.factory import fast_config, tiny_assignments

L = SectionType.L


def test_stage_a_pin_fixes_a_count(tiny: Instance) -> None:
    pinned = replace(tiny, stage_a_pins=(StageAPin("B", "MATH161", L, 1),), _memo={})
    result = run_stage_a(pinned, fast_config())
    assert result.solution is not None
    got = [
        a for a in result.solution.assignments if a.professor_id == "B" and a.course_id == "MATH161"
    ]
    assert len(got) == 1
    assert [v for v in result.violations if v.id == "L4"] == []


def test_stage_b_partial_pins(tiny: Instance) -> None:
    pins = (
        StageBPin("MATH351", L, "1L", "TR0900", None),  # forces C's 361 away from TR0900
        StageBPin("MATH161", L, "2L", None, "7.101"),
    )
    pinned = replace(tiny, stage_b_pins=pins, _memo={})
    result = run_stage_b(pinned, fast_config(), tiny_assignments(pinned))
    assert result.solution is not None and result.solution.placements is not None
    placed = {(p.course_id, p.section_label): p for p in result.solution.placements}
    assert placed[("MATH351", "1L")].pattern_id == "TR0900"
    assert placed[("MATH361", "1L")].pattern_id != "TR0900"
    assert placed[("MATH161", "2L")].room_id == "7.101"
    assert result.violations == []


def test_conflicting_pin_reported_before_solving(tiny: Instance) -> None:
    pinned = replace(tiny, stage_b_pins=(StageBPin("MATH161", L, "1L", None, "7.102"),), _memo={})
    findings = presolve_checks(pinned, fast_config())
    assert any(f.code == "pin_infeasible" and "holds 30 < 40" in f.message for f in findings)
