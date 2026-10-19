"""B4 — Unavailability and blocked slots."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import pattern_blocked, professor_unavailable, room_unavailable
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B4")
def check_b4(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """No placement in a blocked slot (always an error); none at a time the professor is
    unavailable or ranked ``cannot`` (an error in hard mode, a warning in soft mode); none
    in a room at a pattern outside its availability A_r (always an error)."""
    out: list[Violation] = []
    for x in placed_sections(instance, solution):
        if room_unavailable(instance, x.placement.room_id, x.pattern.id):
            out.append(
                Violation(
                    "B4",
                    "error",
                    f"room {x.placement.room_id} is not available at {x.pattern.id} ({x.label})",
                    (x.placement.room_id, x.pattern.id, x.label),
                )
            )
        if pattern_blocked(instance, x.pattern.id):
            out.append(
                Violation(
                    "B4",
                    "error",
                    f"{x.label} meets in a blocked slot ({x.pattern.id})",
                    (x.label, x.pattern.id),
                )
            )
        if professor_unavailable(instance, x.professor_id, x.pattern.id):
            out.append(
                Violation(
                    "B4",
                    severity_for(settings),
                    f"{x.professor_id} is unavailable for {x.label} at {x.pattern.id}",
                    (x.professor_id, x.label, x.pattern.id),
                )
            )
    return out
