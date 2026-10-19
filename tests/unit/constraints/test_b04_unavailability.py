"""B4 — Unavailability and blocked slots."""

from __future__ import annotations

from scheduler.config import Config, Mode
from scheduler.domain import BlockedSlot, Instance, Solution, TimePreference, Unavailability
from scheduler.validation import validate
from tests.factory import asg, instance, offering, plc, prof


def _inst(**kw: object) -> Instance:
    return instance(professors=[prof("P")], offerings=[offering("M101")], **kw)


def _sol(inst: Instance, pattern_id: str) -> Solution:
    return Solution((asg(inst, "P", "M101", "1L"),), (plc("M101", "1L", pattern_id, "R1"),))


def test_b4_available_passes() -> None:
    inst = _inst(unavailability=[Unavailability("P", "Tue", 0, 24 * 60)])
    assert validate(inst, _sol(inst, "MWF0900"), Config(), ids=["B4"]) == []


def test_b4_unavailable_professor() -> None:
    inst = _inst(unavailability=[Unavailability("P", "Wed", 9 * 60 + 30, 11 * 60)])
    vs = validate(inst, _sol(inst, "MWF0900"), Config(), ids=["B4"])
    assert [v.severity for v in vs] == ["error"]
    soft = validate(inst, _sol(inst, "MWF0900"), Config().with_mode("B4", Mode.SOFT), ids=["B4"])
    assert [v.severity for v in soft] == ["warning"]


def test_b4_time_rank_cannot() -> None:
    inst = _inst(time_preferences=[TimePreference("P", "TR0900", None)])
    assert len(validate(inst, _sol(inst, "TR0900"), Config(), ids=["B4"])) == 1


def test_b4_blocked_slot_is_always_an_error() -> None:
    inst = _inst(blocked_slots=[BlockedSlot("Thu", 10 * 60, 11 * 60, "meeting")])
    soft = Config().with_mode("B4", Mode.SOFT)
    vs = validate(inst, _sol(inst, "TR0900"), soft, ids=["B4"])
    assert [(v.severity, "blocked" in v.message) for v in vs] == [("error", True)]


def test_b4_ablation_pair() -> None:
    from tests.factory import ablation_b, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P")],
        offerings=[offering("M101")],
        unavailability=[Unavailability("P", "Mon", 9 * 60, 10 * 60)],
    )
    off, on = ablation_b(inst, (asg(inst, "P", "M101", "1L"),), "B4")
    assert off == ["P is unavailable for M101-1L at MWF0900"]
    assert on == []


def test_b4_soft_prefers_available_time_but_allows_unavailable() -> None:
    from scheduler.pipeline import run_stage_b
    from tests.factory import fast_config, two_pattern_instance

    inst = two_pattern_instance(
        professors=[prof("P")],
        offerings=[offering("M101")],
        unavailability=[Unavailability("P", "Mon", 9 * 60, 10 * 60)],
        blocked_slots=[BlockedSlot("Tue", 9 * 60, 10 * 60, "x")],
    )
    result = run_stage_b(
        inst, fast_config().with_mode("B4", "soft"), (asg(inst, "P", "M101", "1L"),)
    )
    assert result.solution is not None and result.solution.placements is not None
    assert [p.pattern_id for p in result.solution.placements] == ["MWF0900"]
    assert [s.cid for s in result.slacks] == ["B4"]


def _room_limited() -> Instance:
    from scheduler.domain import RoomAvailability
    from tests.factory import two_pattern_instance

    return two_pattern_instance(
        professors=[prof("P")],
        offerings=[offering("M101")],
        room_availability=[RoomAvailability("R1", "TR0900")],
    )


def test_b4_room_availability_validator() -> None:
    inst = _room_limited()
    assert inst.room_patterns == {"R1": frozenset({"TR0900"})}
    [v] = validate(inst, _sol(inst, "MWF0900"), Config(), ids=["B4"])
    assert (v.severity, v.message) == ("error", "room R1 is not available at MWF0900 (M101-1L)")
    assert validate(inst, _sol(inst, "TR0900"), Config(), ids=["B4"]) == []


def test_b4_room_availability_always_filters_f() -> None:
    """Room availability is physical: filtered out of F even with B4 off (SPEC B4)."""
    from scheduler.pipeline import run_stage_b
    from tests.factory import fast_config

    inst = _room_limited()
    sections = (asg(inst, "P", "M101", "1L"),)
    for mode in ("hard", "soft", "off"):
        cfg = fast_config().with_mode("B4", mode)
        result = run_stage_b(inst, cfg, sections, presolve=False)
        assert result.solution is not None and result.solution.placements is not None
        assert [p.pattern_id for p in result.solution.placements] == ["TR0900"], mode
