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


def test_stage_b_inputs_flag_unknown_professor_and_edited_fields() -> None:
    from dataclasses import replace

    inst = instance(professors=[prof("P")], offerings=[offering("M101")])
    good = asg(inst, "P", "M101", "1L")
    codes = {f.code: f for f in presolve_checks(inst, Config(), [replace(good, professor_id="X")])}
    assert codes["unknown_id"].severity == "error" and "'X'" in codes["unknown_id"].message
    placeholder = replace(good, professor_id="TBA-M101")
    assert "unknown_id" not in _codes(inst, assignments=[placeholder])
    edited = presolve_checks(inst, Config(), [replace(good, capacity=good.capacity + 5)])
    mismatch = [f for f in edited if f.code == "assignment_mismatch"]
    assert len(mismatch) == 1 and mismatch[0].severity == "warning"


def test_pre_assignment_above_max_load_is_an_error() -> None:
    """Regression: a pre-assignment over load_max made Stage A infeasible with a clean L1."""
    inst = instance(
        professors=[prof("P", 0, 1)],
        offerings=[offering("M101", n=2)],
        course_preferences=[CoursePreference("P", "M101", 1)],
        pre_assignments=[PreAssignment("P", "M101", SectionType.L, 2)],
    )
    found = [f for f in presolve_checks(inst, Config()) if f.code == "pre_exceeds_caps"]
    assert [f.severity for f in found] == ["error"]
    assert "2 units but the maximum load is 1 (A2)" in found[0].message
    allow_over = Config().model_copy(deep=True)
    allow_over = allow_over.with_mode("A2", "soft")
    a2 = allow_over.constraints["A2"].model_copy(update={"allow_overload": True})
    allow_over = allow_over.model_copy(update={"constraints": {**allow_over.constraints, "A2": a2}})
    assert "pre_exceeds_caps" not in {f.code for f in presolve_checks(inst, allow_over)}
    soft_a4 = Config().with_mode("A4", "soft")
    assert [f.severity for f in presolve_checks(inst, soft_a4) if f.code == "pre_exceeds_caps"] == [
        "warning"
    ]


def test_pre_assignment_against_hard_a5_a6_a8() -> None:
    inst = instance(
        professors=[prof("P", 0, 5, multi_section_pref=-1, max_preps=1)],
        offerings=[offering("M101", n=2), offering("M102")],
        patterns=[pattern("MWF0900", "MWF", "09:00", "09:50")],
        course_preferences=[CoursePreference("P", "M101", 1), CoursePreference("P", "M102", 2)],
        pre_assignments=[
            PreAssignment("P", "M101", SectionType.L, 2),
            PreAssignment("P", "M102", SectionType.L, 1),
        ],
    )
    cfg = Config().with_mode("A5", "hard").with_mode("A6", "hard")
    msgs = [f.message for f in presolve_checks(inst, cfg) if f.code == "pre_exceeds_caps"]
    assert any("(A8)" in m for m in msgs)
    assert any("2 sections of M101" in m and "(A5)" in m for m in msgs)
    assert any("2 different courses" in m and "(A6)" in m for m in msgs)
    assert not any(
        f.code == "pre_exceeds_caps"
        for f in presolve_checks(inst, Config().with_mode("A8", "soft"))
    )
