"""B8 — Max teaching days."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution, TimePreference
from scheduler.validation import validate
from tests.factory import ablation_b, asg, instance, offering, pattern, plc, prof, room

PATTERNS = [
    pattern("MWF0900", "MWF", "09:00", "09:50"),
    pattern("MWF1000", "MWF", "10:00", "10:50"),
    pattern("TR0900", "TR", "09:00", "10:15"),
    pattern("TR1030", "TR", "10:30", "11:45"),
]


def _inst() -> Instance:
    return instance(
        professors=[prof("P", max_days=2)],
        offerings=[offering("M1"), offering("M2")],
        rooms=[room("R1")],
        patterns=PATTERNS,
        time_preferences=[TimePreference("P", t.id, i + 1) for i, t in enumerate(PATTERNS)],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"))


def test_b8_validator() -> None:
    inst = _inst()
    sol = Solution(
        _sections(inst), (plc("M1", "1L", "MWF0900", "R1"), plc("M2", "1L", "TR0900", "R1"))
    )
    assert [v.message for v in validate(inst, sol, Config(), ids=["B8"])] == [
        "P teaches on 5 days (Mon Tue Wed Thu Fri), more than 2"
    ]


def test_b8_ablation_pair() -> None:
    inst = _inst()
    off, on = ablation_b(inst, _sections(inst), "B8", on_mode="soft")
    assert off == ["P teaches on 3 days (Mon Wed Fri), more than 2"]
    assert on == []
