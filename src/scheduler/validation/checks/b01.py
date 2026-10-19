"""B1 — Section scheduled once, into a feasible (pattern, room)."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import pattern_problem, room_problem
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import stage_b


@check("B1")
def check_b1(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_{t,r} y_{s,t,r} = 1 for every assigned section; each placement must be a feasible
    combination of room capacity/type and pattern section type/teaching days.

    Room and pattern fit has no constraint ID of its own in SPEC §4 (it is part of the
    feasible set F); it is checked here because a placement outside F is not a valid
    scheduling of the section.
    """
    out: list[Violation] = []
    sections = stage_b(instance, solution)
    placements = solution.placements or ()
    counts = Counter(p.section_key for p in placements)
    for key, sec in sections.items():
        n = counts.get(key, 0)
        if n == 0:
            out.append(
                Violation("B1", severity_for(settings), f"{sec.id} is not scheduled", (sec.id,))
            )
        elif n > 1:
            out.append(
                Violation("B1", "error", f"{sec.id} is scheduled {n} times", (sec.id,), n - 1)
            )
    for p in placements:
        sid = f"{p.course_id}-{p.section_label}"
        placed = sections.get(p.section_key)
        if placed is None:
            out.append(
                Violation("B1", "error", f"{sid} is scheduled but not assigned to anyone", (sid,))
            )
            continue
        pattern = instance.pattern_by_id.get(p.pattern_id)
        room = instance.room_by_id.get(p.room_id)
        problems: list[str | None] = []
        if pattern is None:
            problems.append(f"unknown pattern {p.pattern_id}")
        else:
            problems.append(pattern_problem(instance, config, placed.section, pattern))
        if room is None:
            problems.append(f"unknown room {p.room_id}")
        else:
            problems.append(room_problem(placed.section, room))
        for msg in problems:
            if msg is not None:
                out.append(
                    Violation("B1", "error", f"{sid}: {msg}", (sid, p.pattern_id, p.room_id))
                )
    return out
