"""B11 — Room stability."""

from __future__ import annotations

from collections import defaultdict

from scheduler.config import B11Settings, Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check
from scheduler.validation.view import placed_sections


@check("B11")
def check_b11(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """B11 only rewards fewer rooms per professor (minimize sum_r gamma_{p,r}); it cannot be
    violated. The check reports professors teaching in more than one room (or building,
    with ``scope: building``) as warnings, sized by the number of extra rooms."""
    building = isinstance(settings, B11Settings) and settings.scope == "building"
    used: dict[str, set[str]] = defaultdict(set)
    for x in placed_sections(instance, solution):
        if x.section.placeholder:
            continue
        room = instance.room_by_id[x.placement.room_id]
        used[x.professor_id].add(room.building if building else room.id)
    kind = "buildings" if building else "rooms"
    return [
        Violation(
            "B11",
            "warning",
            f"{pid} teaches in {len(places)} {kind} ({', '.join(sorted(places))})",
            (pid,),
            size=len(places) - 1,
        )
        for pid, places in sorted(used.items())
        if len(places) > 1
    ]
