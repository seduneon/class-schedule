"""B6 — Spread sections of a course."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution
from scheduler.validation import validate
from tests.factory import ablation_b, asg, offering, plc, prof, room, two_pattern_instance


def _inst() -> Instance:
    return two_pattern_instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("M101", n=2)],
        rooms=[room("R1"), room("R2")],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M101", "1L"), asg(inst, "Q", "M101", "2L"))


def test_b6_validator() -> None:
    inst = _inst()
    same = Solution(
        _sections(inst), (plc("M101", "1L", "MWF0900", "R1"), plc("M101", "2L", "MWF0900", "R2"))
    )
    vs = validate(inst, same, Config(), ids=["B6"])
    assert [(v.severity, v.entities) for v in vs] == [("warning", ("M101 L", "M101-1L", "M101-2L"))]
    apart = Solution(
        _sections(inst), (plc("M101", "1L", "MWF0900", "R1"), plc("M101", "2L", "TR0900", "R2"))
    )
    assert validate(inst, apart, Config(), ids=["B6"]) == []


def test_b6_ablation_pair() -> None:
    inst = _inst()
    off, on = ablation_b(inst, _sections(inst), "B6", on_mode="soft")
    assert len(off) == 1 and on == []
