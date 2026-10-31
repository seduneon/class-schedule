"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import (
    CoursePreference,
    FamilyMixing,
    Instance,
    Offering,
    Professor,
    Solution,
    Unavailability,
)
from scheduler.validation import validate
from tests.factory import ablation_a, asg, instance, offering, pattern, prof, room


def _inst() -> Instance:
    return instance(
        professors=[prof("P", 0, 3), prof("Q", 0, 10)],
        offerings=[offering("M1", n=2)],
        unavailability=[Unavailability("P", "Tue", 0, 24 * 60)],  # P can only use MWF0900
        course_preferences=[CoursePreference("P", "M1", 1), CoursePreference("Q", "M1", 2)],
    )


def test_a8_validator() -> None:
    inst = _inst()
    sol = Solution((asg(inst, "P", "M1", "1L"), asg(inst, "P", "M1", "2L")))
    assert [v.message for v in validate(inst, sol, Config(), ids=["A8"])] == [
        "P has 2 sections but only 1 non-overlapping available time patterns"
    ]


def test_a8_ablation_pair() -> None:
    off, on = ablation_a(_inst(), "A8")
    assert len(off) == 1 and on == []


# ----- day families (B13 hard, SPEC D11) ---------------------------------------------

FAMILY_PATTERNS = [
    pattern("MWF0900", "MWF", "09:00", "09:50"),
    pattern("MWF1000", "MWF", "10:00", "10:50"),
    pattern("TR0900", "TR", "09:00", "10:15"),
    pattern("TR1030", "TR", "10:30", "11:45"),
]
TR = frozenset({"TR"})


def _family_inst(profs: list[Professor], offerings: list[Offering], **kw: object) -> Instance:
    prefs = [CoursePreference(p.id, o.course_id, 1) for p in profs for o in offerings]
    return instance(
        professors=profs,
        offerings=offerings,
        patterns=FAMILY_PATTERNS,
        course_preferences=prefs,
        **kw,
    )


def _messages(inst: Instance, sol: Solution, b13: str = "hard") -> list[str]:
    return [v.message for v in validate(inst, sol, Config().with_mode("B13", b13), ids=["A8"])]


def test_a8_alpha_keeps_only_preferred_family() -> None:
    rooms = [room("R1"), room("R2")]  # 4 TR slots: only alpha_p binds
    inst = _family_inst([prof("P", day_families=TR)], [offering("M1", n=3)], rooms=rooms)
    sol = Solution(tuple(asg(inst, "P", "M1", f"{i}L") for i in (1, 2, 3)))
    assert _messages(inst, sol) == [
        "P has 3 sections but only 2 non-overlapping available time patterns"
    ]
    assert _messages(inst, sol, b13="soft") == []  # all 4 patterns count


def test_a8_alpha_one_family_when_mixing_forbidden() -> None:
    p = prof("P", day_families=frozenset({"MWF", "TR"}), day_family_mixing=FamilyMixing.FORBID)
    inst = _family_inst([p], [offering("M1", n=3)])
    sol = Solution(tuple(asg(inst, "P", "M1", f"{i}L") for i in (1, 2, 3)))
    assert _messages(inst, sol) == [
        "P has 3 sections but only 2 non-overlapping available time patterns"
    ]


def test_a8_family_room_slots() -> None:
    inst = _family_inst(
        [prof("P", day_families=TR), prof("Q", day_families=TR)], [offering("M1", n=3)]
    )
    sol = Solution(
        (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M1", "2L"), asg(inst, "Q", "M1", "3L"))
    )
    assert _messages(inst, sol) == [
        "professors who teach only TR have 3 sections that fit only in rooms R1, which have 2 TR "
        "(room, time pattern) slots"
    ]


def test_a8_family_conflict_group() -> None:
    courses = [offering(c, level=300) for c in ("M301", "M302", "M303")]
    profs = [prof(p, day_families=TR) for p in ("P", "Q", "S")]
    inst = _family_inst(profs, courses, rooms=[room("R1"), room("R2")])
    sol = Solution(
        (asg(inst, "P", "M301", "1L"), asg(inst, "Q", "M302", "1L"), asg(inst, "S", "M303", "1L"))
    )
    assert _messages(inst, sol) == [
        "conflict group level_300 needs 3 non-overlapping TR time patterns for professors who "
        "teach only TR but only 2 exist"
    ]


def test_a8_ablation_pair_family_rooms() -> None:
    # P and Q (TR only) rank M1 first, S (any day) second: only 2 TR slots for 3 sections.
    profs = [prof("P", 0, 2, day_families=TR), prof("Q", 0, 2, day_families=TR), prof("S")]
    inst = instance(
        professors=profs,
        offerings=[offering("M1", n=3)],
        patterns=FAMILY_PATTERNS,
        course_preferences=[
            CoursePreference("P", "M1", 1),
            CoursePreference("Q", "M1", 1),
            CoursePreference("S", "M1", 2),
        ],
    )
    off, on = ablation_a(inst, "A8")
    assert off == [
        "professors who teach only TR have 3 sections that fit only in rooms R1, which have 2 TR "
        "(room, time pattern) slots"
    ]
    assert on == []


def test_a8_ablation_pair_family_group() -> None:
    courses = [offering(c, level=300) for c in ("M301", "M302", "M303")]
    profs = [prof(p, 0, 1, day_families=TR) for p in ("P", "Q", "S")] + [prof("T", 0, 1)]
    prefs = [CoursePreference(p, c.course_id, 1) for p in ("P", "Q", "S") for c in courses]
    prefs += [CoursePreference("T", c.course_id, 2) for c in courses]
    inst = instance(
        professors=profs,
        offerings=courses,
        patterns=FAMILY_PATTERNS,
        rooms=[room("R1"), room("R2")],
        course_preferences=prefs,
    )
    off, on = ablation_a(inst, "A8")
    assert off == [
        "conflict group level_300 needs 3 non-overlapping TR time patterns for professors who "
        "teach only TR but only 2 exist"
    ]
    assert on == []


def test_a8_family_room_size() -> None:
    # 4 TR slots in total, but only Big (2 TR slots) holds the 100-seat course.
    inst = _family_inst(
        [prof("P", 0, 2, day_families=TR), prof("Q", 0, 2, day_families=TR)],
        [offering("M1", n=3, cap=100)],
        rooms=[room("Big", cap=120), room("Small", cap=40)],
    )
    sol = Solution(
        (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M1", "2L"), asg(inst, "Q", "M1", "3L"))
    )
    assert _messages(inst, sol) == [
        "professors who teach only TR have 3 sections that fit only in rooms Big, which have 2 TR "
        "(room, time pattern) slots"
    ]


def test_a8_family_group_counts_one_professors_sections() -> None:
    # P's two M301 sections cannot overlap (B3), and M302 may not overlap M301 (B5).
    courses = [offering("M301", n=2, level=300), offering("M302", level=300)]
    profs = [prof("P", day_families=TR), prof("Q", day_families=TR)]
    inst = _family_inst(profs, courses, rooms=[room("R1"), room("R2")])
    sol = Solution(
        (asg(inst, "P", "M301", "1L"), asg(inst, "P", "M301", "2L"), asg(inst, "Q", "M302", "1L"))
    )
    assert _messages(inst, sol) == [
        "conflict group level_300 needs 3 non-overlapping TR time patterns for professors who "
        "teach only TR but only 2 exist"
    ]
    split = Solution(
        (asg(inst, "P", "M301", "1L"), asg(inst, "Q", "M301", "2L"), asg(inst, "P", "M302", "1L"))
    )
    assert _messages(inst, split) == []  # M301-1L and M301-2L may share a pattern
