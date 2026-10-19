"""L1 — pre-solve diagnostics."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.diagnostics import has_errors, presolve_checks
from scheduler.domain import (
    BlockedSlot,
    CoursePreference,
    Instance,
    PreAssignment,
    SectionType,
    StageBPin,
    TimePreference,
    Unavailability,
)
from tests.factory import asg, instance, offering, pattern, prof, room


def _codes(inst: Instance, **kw: object) -> set[str]:
    return {f.code for f in presolve_checks(inst, Config(), **kw)}  # type: ignore[arg-type]


def test_tiny_is_clean(tiny: Instance) -> None:
    findings = presolve_checks(tiny, Config())
    assert not has_errors(findings), findings


def test_load_capacity_and_no_eligible_professor() -> None:
    inst = instance(
        professors=[prof("P", 0, 1)],
        offerings=[offering("M101", n=2), offering("M102")],
        course_preferences=[CoursePreference("P", "M101", 1)],
    )
    codes = _codes(inst)
    assert {"load_capacity", "no_eligible_professor", "eligible_capacity"} <= codes


def test_no_room_and_no_pattern() -> None:
    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M101", cap=500), offering("M102", kind="LAB", room_type="lab")],
        patterns=[pattern("MWF0900", "MWF", "09:00", "09:50", types="L")],
        course_preferences=[CoursePreference("P", "M101", 1), CoursePreference("P", "M102", 2)],
    )
    msgs = [
        f.message for f in presolve_checks(inst, Config()) if f.code in ("no_room", "no_pattern")
    ]
    assert any("M101 L (capacity 500" in m for m in msgs)
    assert any("M102 LAB: no usable time pattern" in m for m in msgs)


def test_data_integrity() -> None:
    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M101")],
        course_preferences=[CoursePreference("P", "M101", 1), CoursePreference("X", "M999", 1)],
        time_preferences=[TimePreference("P", "MWF0900", 1), TimePreference("P", "TR0900", 1)],
        pre_assignments=[
            PreAssignment("P", "M555", SectionType.L, 1),
            PreAssignment("P", "M101", SectionType.L, 2),
        ],
        blocked_slots=[BlockedSlot("Mon", 600, 700, "a"), BlockedSlot("Mon", 650, 720, "b")],
    )
    codes = _codes(inst)
    assert {
        "unknown_id",
        "duplicate_rank",
        "pre_not_offered",
        "pre_exceeds_sections",
        "overlapping_blocked_slots",
    } <= codes


def test_alpha_and_group_capacity() -> None:
    inst = instance(
        professors=[prof("P", 2, 3)],
        offerings=[offering("M301"), offering("M302"), offering("M303")],
        patterns=[
            pattern("MWF0900", "MWF", "09:00", "09:50"),
            pattern("MWF0930", "MWF", "09:30", "10:20"),
        ],
        unavailability=[Unavailability("P", "Mon", 9 * 60, 9 * 60 + 40)],
        course_preferences=[
            CoursePreference("P", c, i + 1) for i, c in enumerate(["M301", "M302", "M303"])
        ],
    )
    findings = {f.code: f for f in presolve_checks(inst, Config())}
    assert "alpha" in findings  # P is available only for MWF0930 (alpha = 1) but needs 2 sections
    assert "only 1 pairwise non-overlapping" in findings["group_capacity"].message


def test_pins_and_stage_b_inputs() -> None:
    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M101", cap=60)],
        rooms=[room("Small", cap=20)],
        stage_b_pins=[StageBPin("M101", SectionType.L, "1L", "MWF0900", "Small")],
        course_preferences=[CoursePreference("P", "M101", 1)],
    )
    codes = _codes(inst, assignments=[asg(inst, "P", "M101", "1L")])
    assert {"pin_infeasible", "no_feasible_slot", "no_room"} <= codes


def test_room_slots_shortfall_with_room_availability() -> None:
    from scheduler.domain import RoomAvailability
    from tests.factory import room

    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M101", n=2, cap=150)],
        rooms=[room("Big", cap=200), room("Small", cap=40)],
        room_availability=[RoomAvailability("Big", "MWF0900")],
    )
    [f] = [f for f in presolve_checks(inst, Config()) if f.code == "room_slots"]
    assert f.severity == "error"
    assert f.message.startswith("2 section(s) need a room with >= 150 seats, but only 1")
