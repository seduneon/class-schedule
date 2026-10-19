"""B2 — No room overlap."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import overlapping_pairs, placed_sections


@check("B2")
def check_b2(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """No two placements in the same room with overlapping patterns
    (sum_s sum_{t in Q} y_{s,t,r} <= 1 for every clique Q)."""
    placed = placed_sections(instance, solution)
    return [
        Violation(
            "B2",
            severity_for(settings),
            f"room {room} is double-booked: {a.label} ({a.pattern.id}) and {b.label} ({b.pattern.id})",
            (room, a.label, b.label),
        )
        for room, a, b in overlapping_pairs(placed, config, lambda x: x.placement.room_id)
    ]
