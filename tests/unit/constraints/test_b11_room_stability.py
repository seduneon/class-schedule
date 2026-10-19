"""B11 — Room stability."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, Solution
from scheduler.pipeline import run_stage_b
from scheduler.validation import validate
from tests.factory import asg, fast_config, offering, plc, prof, room, two_pattern_instance


def _inst() -> Instance:
    return two_pattern_instance(
        professors=[prof("P")],
        offerings=[offering("M1"), offering("M2")],
        rooms=[room("R1"), room("R2")],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"))


def test_b11_validator() -> None:
    inst = _inst()
    two = Solution(
        _sections(inst), (plc("M1", "1L", "MWF0900", "R1"), plc("M2", "1L", "TR0900", "R2"))
    )
    cfg = Config().with_mode("B11", "soft")
    assert [(v.severity, v.size) for v in validate(inst, two, cfg, ids=["B11"])] == [("warning", 1)]
    by_building = Config.model_validate(
        {"constraints": {"B11": {"mode": "soft", "scope": "building"}}}
    )
    assert validate(inst, two, by_building, ids=["B11"]) == []


def test_b11_ablation_pair() -> None:
    """B11 only rewards; with it on the professor always stays in one room. (Off, the room
    choice is arbitrary, so the 'off' half only checks the run is valid.)"""
    inst = _inst()
    cfg = fast_config()
    on = run_stage_b(inst, cfg.with_mode("B11", "soft"), _sections(inst), presolve=False)
    off = run_stage_b(inst, cfg.with_mode("B11", "off"), _sections(inst), presolve=False)
    assert on.solution is not None and off.solution is not None
    check_cfg = cfg.with_mode("B11", "soft")
    assert validate(inst, on.solution, check_cfg, ids=["B11"]) == []
    assert len(validate(inst, off.solution, check_cfg, ids=["B11"])) <= 1
