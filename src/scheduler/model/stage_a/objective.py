"""Stage A objective levels (SPEC §5.3).

Level 1 (min): uncovered sections (A1 slacks).
Level 2 (min): weighted soft slacks (A2, A5, A6, ...).
Level 3 (max): sum_p pi_p sat^C_p + lambda^C m^C (A9) + A5 bonus.
"""

from __future__ import annotations

from scheduler.config import Config
from scheduler.model.context import (
    LEVEL_COVERAGE,
    LEVEL_SATISFACTION,
    LEVEL_SOFT,
    ModelContext,
    ObjectiveLevel,
)
from scheduler.model.stage_a.variables import course_satisfaction


def stage_a_levels(config: Config) -> list[ObjectiveLevel]:
    tol = config.objective.tolerances
    return [
        ObjectiveLevel(LEVEL_COVERAGE, "coverage", "min", tol.level1),
        ObjectiveLevel(LEVEL_SOFT, "soft", "min", tol.level2),
        ObjectiveLevel(LEVEL_SATISFACTION, "satisfaction", "max", 0.0),
    ]


def add_satisfaction_terms(ctx: ModelContext) -> None:
    """Level 3 base term: sum_p pi_p sat^C_p (priority applies to course satisfaction, D6)."""
    for p in ctx.instance.professors:
        sat = course_satisfaction(ctx, p.id)
        if sat is not None:
            ctx.add_objective_term(LEVEL_SATISFACTION, p.priority * sat, f"sat_C[{p.id}]")
