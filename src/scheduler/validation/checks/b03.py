"""B3 — No professor overlap (placeholder instructors are exempt)."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import overlapping_pairs, placed_sections, professor_key


@check("B3")
def check_b3(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """No professor teaches two placements with overlapping patterns
    (sum_{t in Q} busy_{p,t} <= 1)."""
    placed = placed_sections(instance, solution)
    return [
        Violation(
            "B3",
            severity_for(settings),
            f"{prof} teaches {a.label} ({a.pattern.id}) and {b.label} ({b.pattern.id}) at the same time",
            (prof, a.label, b.label),
        )
        for prof, a, b in overlapping_pairs(placed, config, professor_key)
    ]
