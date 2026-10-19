"""B6 — Spread sections of a course."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import overlapping_pairs, placed_sections


@check("B6")
def check_b6(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Sections of the same (course, type) should not overlap
    (sum_{s in (c,k)} sum_{t in Q} sum_r y_{s,t,r} <= 1)."""
    placed = placed_sections(instance, solution)
    return [
        Violation(
            "B6",
            severity_for(settings),
            f"{a.label} and {b.label} of {key} overlap ({a.pattern.id}, {b.pattern.id})",
            (key, a.label, b.label),
        )
        for key, a, b in overlapping_pairs(
            placed,
            config,
            lambda x: f"{x.course_id} {x.section.section.section_type.value}",
        )
        if a.placement.section_key != b.placement.section_key
    ]
