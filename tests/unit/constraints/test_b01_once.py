"""B1 — Section scheduled once."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution
from scheduler.validation import validate
from tests.factory import plc, tiny_solution, with_placements


def _b1(inst: Instance, sol: Solution) -> list[str]:
    return [v.message for v in validate(inst, sol, Config(), ids=["B1"])]


def test_b1_valid_solution_passes(tiny: Instance) -> None:
    assert _b1(tiny, tiny_solution(tiny)) == []


def test_b1_unscheduled_and_double_scheduled(tiny: Instance) -> None:
    sol = tiny_solution(tiny)
    missing = Solution(sol.assignments, sol.placements[1:])  # type: ignore[index]
    assert _b1(tiny, missing) == ["MATH161-1L is not scheduled"]
    twice = Solution(sol.assignments, (*sol.placements, plc("MATH361", "1L", "MWF1000", "7.102")))  # type: ignore[misc]
    assert _b1(tiny, twice) == ["MATH361-1L is scheduled 2 times"]


def test_b1_room_and_pattern_must_fit(tiny: Instance) -> None:
    small_room = with_placements(tiny_solution(tiny), plc("MATH161", "1L", "MWF0900", "7.102"))
    assert _b1(tiny, small_room) == ["MATH161-1L: room 7.102 holds 30 < 40"]
    unknown = with_placements(tiny_solution(tiny), plc("MATH351", "1L", "XX", "7.102"))
    assert _b1(tiny, unknown) == ["MATH351-1L: unknown pattern XX"]


def test_b1_ablation_pair() -> None:
    from tests.factory import ablation_b, asg, offering, prof, two_pattern_instance

    inst = two_pattern_instance(professors=[prof("P")], offerings=[offering("M101")])
    off, on = ablation_b(inst, (asg(inst, "P", "M101", "1L"),), "B1")
    assert off == ["M101-1L is scheduled 2 times"]
    assert on == []
