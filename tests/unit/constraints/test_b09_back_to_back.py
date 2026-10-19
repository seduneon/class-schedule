"""B9 — Back-to-back preference."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, ScheduleStyle, Solution, TimePreference
from scheduler.pipeline import run_stage_b
from scheduler.validation import validate
from tests.factory import ablation_b, asg, fast_config, instance, offering, pattern, plc, prof, room

PATTERNS = [
    pattern("MWF0900", "MWF", "09:00", "09:50"),
    pattern("MWF1000", "MWF", "10:00", "10:50"),
    pattern("MWF1100", "MWF", "11:30", "12:20"),
]


def _inst(style: ScheduleStyle, ranks: dict[str, int]) -> Instance:
    return instance(
        professors=[prof("P", schedule_style=style)],
        offerings=[offering("M1"), offering("M2")],
        rooms=[room("R1")],
        patterns=PATTERNS,
        time_preferences=[TimePreference("P", t, r) for t, r in ranks.items()],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"))


def test_b9_validator_spread() -> None:
    inst = _inst(ScheduleStyle.SPREAD, {"MWF0900": 1, "MWF1000": 2})
    sol = Solution(
        _sections(inst), (plc("M1", "1L", "MWF0900", "R1"), plc("M2", "1L", "MWF1000", "R1"))
    )
    assert [v.message for v in validate(inst, sol, Config(), ids=["B9"])] == [
        "P prefers spread-out teaching but has back-to-back MWF0900 -> MWF1000"
    ]
    compact = _inst(ScheduleStyle.COMPACT, {})
    assert validate(compact, sol, Config(), ids=["B9"]) == []


def test_b9_ablation_pair_spread() -> None:
    inst = _inst(ScheduleStyle.SPREAD, {"MWF0900": 1, "MWF1000": 2, "MWF1100": 3})
    off, on = ablation_b(inst, _sections(inst), "B9", on_mode="soft")
    assert len(off) == 1 and on == []


def test_b9_compact_reward_pulls_sections_together() -> None:
    inst = _inst(ScheduleStyle.COMPACT, {"MWF0900": 1, "MWF1100": 2, "MWF1000": 3})
    cfg = fast_config().with_updates(constraints={"B9": {"mode": "soft", "reward": 1.0}})
    result = run_stage_b(inst, cfg, _sections(inst), presolve=False)
    assert result.solution is not None and result.solution.placements is not None
    assert {p.pattern_id for p in result.solution.placements} == {"MWF0900", "MWF1000"}
