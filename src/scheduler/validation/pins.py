"""L4 — pins are honoured by a solution (not a §4 constraint, so not in the registry)."""

from __future__ import annotations

from collections import Counter

from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation


def check_pins(instance: Instance, solution: Solution) -> list[Violation]:
    """Stage A pins fix counts exactly; Stage B pins fix the pattern and/or room."""
    out: list[Violation] = []
    counts = Counter((a.professor_id, a.course_id, a.section_type) for a in solution.assignments)
    for pin in instance.stage_a_pins:
        have = counts.get((pin.professor_id, pin.course_id, pin.section_type), 0)
        if have != pin.count:
            out.append(
                Violation(
                    "L4",
                    "error",
                    f"pin: {pin.professor_id} should teach {pin.count} {pin.course_id} "
                    f"{pin.section_type.value} section(s), has {have}",
                    (pin.professor_id, pin.course_id),
                )
            )
    if solution.placements is None:
        return out
    placed = {p.section_key: p for p in solution.placements}
    for bpin in instance.stage_b_pins:
        key = (bpin.course_id, bpin.section_type, bpin.section_label)
        sid = f"{bpin.course_id}-{bpin.section_label}"
        got = placed.get(key)
        if got is None:
            continue  # unscheduled sections are B1's concern
        if bpin.pattern_id is not None and got.pattern_id != bpin.pattern_id:
            out.append(
                Violation(
                    "L4",
                    "error",
                    f"pin: {sid} should meet at {bpin.pattern_id}, meets at {got.pattern_id}",
                    (sid,),
                )
            )
        if bpin.room_id is not None and got.room_id != bpin.room_id:
            out.append(
                Violation(
                    "L4",
                    "error",
                    f"pin: {sid} should be in room {bpin.room_id}, is in {got.room_id}",
                    (sid,),
                )
            )
    return out
