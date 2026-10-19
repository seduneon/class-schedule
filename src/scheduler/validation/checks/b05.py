"""B5 — Conflict groups: different courses of a group never overlap."""

from __future__ import annotations

import itertools

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import conflict_groups
from scheduler.domain import Instance, Solution
from scheduler.time import patterns_overlap
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B5")
def check_b5(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """For each group g, flag overlapping placements of two *different* courses of g.
    Sections of the same course may overlap."""
    out: list[Violation] = []
    placed = placed_sections(instance, solution)
    for g in conflict_groups(instance, config):
        members = [x for x in placed if x.course_id in g.course_ids]
        for a, b in itertools.combinations(members, 2):
            if a.course_id != b.course_id and patterns_overlap(
                a.pattern, b.pattern, config.time.buffer_minutes
            ):
                out.append(
                    Violation(
                        "B5",
                        severity_for(g.mode),
                        f"conflict group {g.id}: {a.label} ({a.pattern.id}) overlaps "
                        f"{b.label} ({b.pattern.id})",
                        (g.id, a.label, b.label),
                    )
                )
    return out
