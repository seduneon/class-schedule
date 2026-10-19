"""L3 alternatives and L5 repair."""

from __future__ import annotations

import itertools
from dataclasses import replace

import pytest

from scheduler.domain import Instance, Room, Unavailability
from scheduler.pipeline import alternatives, run_stage_a, run_stage_b
from scheduler.validation import validate
from tests.factory import fast_config, tiny_assignments, tiny_solution


def test_stage_b_alternatives_differ_and_stay_near_optimal(tiny: Instance) -> None:
    cfg = fast_config(alternatives={"count": 3, "min_difference": 2, "optimality_gap": 0.25})
    best = run_stage_b(tiny, cfg, tiny_assignments(tiny))
    assert best.solution is not None
    alts = alternatives(best, cfg)
    assert alts, "expected at least one alternative within 25%"
    best_value = best.objective(3)
    for alt in alts:
        assert alt.objective >= best_value * 0.75 - 1e-6
        assert alt.diff, "an alternative must differ in at least one time choice"
        assert [v for v in validate(tiny, alt.solution, cfg) if v.severity == "error"] == []
        assert any("room" not in line for line in alt.diff)  # rooms alone never count
    assert [a.rank for a in alts] == list(range(1, len(alts) + 1))
    assert all(a.objective >= b.objective for a, b in itertools.pairwise(alts))


def test_stage_a_alternatives_change_who_teaches_what(tiny: Instance) -> None:
    cfg = fast_config(alternatives={"count": 2, "min_difference": 2, "optimality_gap": 1.0})
    best = run_stage_a(tiny, cfg)
    alts = alternatives(best, cfg)
    assert alts
    assert all(alt.diff for alt in alts)
    # level 1 stays optimal: every section covered
    for alt in alts:
        assert len(alt.solution.assignments) == 4


def test_no_alternative_within_zero_gap_when_optimum_is_unique(tiny: Instance) -> None:
    cfg = fast_config(alternatives={"count": 2, "min_difference": 2, "optimality_gap": 0.0})
    best = run_stage_a(tiny, cfg)
    assert alternatives(best, cfg) == []


def test_repair_stage_b_moves_as_little_as_possible(tiny: Instance) -> None:
    previous = tiny_solution(tiny)
    # C becomes unavailable on Tuesday mornings: MATH361 must leave TR0900.
    changed = replace(tiny, unavailability=(Unavailability("C", "Tue", 8 * 60, 12 * 60),), _memo={})
    result = run_stage_b(changed, fast_config(), previous.assignments, previous=previous)
    assert result.solution is not None and result.solution.placements is not None
    assert result.objective(10) == pytest.approx(1)  # exactly one section moved
    moved = set(result.solution.placements) - set(previous.placements or ())
    assert {(p.course_id, p.section_label) for p in moved} == {("MATH361", "1L")}


def test_repair_stage_a_keeps_previous_assignment(tiny: Instance) -> None:
    previous = run_stage_a(tiny, fast_config()).solution
    assert previous is not None
    bigger = replace(tiny, rooms=(*tiny.rooms, Room("7.103", "Block 7", 60, "lecture")), _memo={})
    result = run_stage_a(bigger, fast_config(), previous=previous)
    assert result.objective(10) == pytest.approx(0)
    assert result.solution is not None
    assert set(result.solution.assignments) == set(previous.assignments)
