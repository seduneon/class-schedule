"""B10 — Max consecutive teaching."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution, TimePreference
from scheduler.validation import validate
from tests.factory import ablation_b, asg, instance, offering, pattern, plc, prof, room

PATTERNS = [
    pattern("MWF0800", "MWF", "08:00", "08:50"),
    pattern("MWF0900", "MWF", "09:00", "09:50"),
    pattern("MWF1000", "MWF", "10:00", "10:50"),
    pattern("MWF1400", "MWF", "14:00", "14:50"),
]
CFG = Config.model_validate({"constraints": {"B10": {"mode": "hard", "max_consecutive": 2}}})


def _inst() -> Instance:
    return instance(
        professors=[prof("P")],
        offerings=[offering("M1"), offering("M2"), offering("M3")],
        rooms=[room("R1")],
        patterns=PATTERNS,
        time_preferences=[TimePreference("P", t.id, i + 1) for i, t in enumerate(PATTERNS)],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"), asg(inst, "P", "M3", "1L"))


def test_b10_validator() -> None:
    inst = _inst()
    three = Solution(
        _sections(inst),
        (
            plc("M1", "1L", "MWF0800", "R1"),
            plc("M2", "1L", "MWF0900", "R1"),
            plc("M3", "1L", "MWF1000", "R1"),
        ),
    )
    assert [v.message for v in validate(inst, three, CFG, ids=["B10"])] == [
        "P teaches 3 back-to-back patterns (MWF0800 -> MWF0900 -> MWF1000), more than 2"
    ]


def test_b10_ablation_pair() -> None:
    inst = _inst()
    off, on = ablation_b(inst, _sections(inst), "B10", cfg=CFG.with_updates(solver={"threads": 1}))
    assert len(off) == 1 and on == []
