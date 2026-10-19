"""B7 — Recitation–lecture relation."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import Instance, SectionLink, Solution, TimePreference
from scheduler.validation import validate
from tests.factory import (
    ablation_b,
    asg,
    fast_config,
    instance,
    offering,
    pattern,
    plc,
    prof,
    room,
    two_pattern_instance,
)


def _inst() -> Instance:
    return two_pattern_instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("C1"), offering("C1", kind="R")],
        rooms=[room("R1"), room("R2")],
        section_links=[SectionLink("C1", "1R", "1L")],
    )


def _sections(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "C1", "1L"), asg(inst, "Q", "C1", "1R"))


def test_b7_validator() -> None:
    inst = _inst()
    clash = Solution(
        _sections(inst), (plc("C1", "1L", "MWF0900", "R1"), plc("C1", "1R", "MWF0900", "R2"))
    )
    assert [v.message for v in validate(inst, clash, Config(), ids=["B7"])] == [
        "recitation C1-1R overlaps lecture C1-1L"
    ]


def test_b7_ablation_pair() -> None:
    inst = _inst()
    off, on = ablation_b(inst, _sections(inst), "B7", on_mode="soft")
    assert off == ["recitation C1-1R overlaps lecture C1-1L"] and on == []


def test_b7_recitation_after_first_lecture() -> None:
    inst = instance(
        professors=[prof("P"), prof("Q")],
        offerings=[offering("C1"), offering("C1", kind="R")],
        rooms=[room("R1")],
        patterns=[
            pattern("MW0900", "MW", "09:00", "10:15"),
            pattern("TR0900", "TR", "09:00", "10:15"),
            pattern("F0900", "F", "09:00", "09:50"),
        ],
        time_preferences=[
            TimePreference("P", "TR0900", 1),
            TimePreference("Q", "MW0900", 1),
            TimePreference("Q", "F0900", 2),
        ],
    )
    cfg = Config.model_validate(
        {"constraints": {"B7": {"mode": "soft", "recitation_after_first_lecture": True}}}
    )
    early = Solution(
        _sections(inst), (plc("C1", "1L", "TR0900", "R1"), plc("C1", "1R", "MW0900", "R1"))
    )
    assert any(
        "starts the week before" in v.message for v in validate(inst, early, cfg, ids=["B7"])
    )
    off, on = ablation_b(
        inst,
        _sections(inst),
        "B7",
        on_mode="soft",
        cfg=fast_config().with_updates(constraints={"B7": cfg.settings("B7").model_dump()}),
    )
    assert off and on == []
