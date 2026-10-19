"""Stage B objective levels (SPEC §6.3).

Level 1 (min): unscheduled sections (B1 slacks).
Level 2 (min): weighted soft slacks (B4-B11 in soft mode).
Level 3 (max): sum_p pi_p sat^T_p + lambda^T m^T (B12) + B9 compact reward - B11 room count.
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
from scheduler.model.stage_b.variables import professors, time_satisfaction


def stage_b_levels(config: Config) -> list[ObjectiveLevel]:
    tol = config.objective.tolerances
    return [
        ObjectiveLevel(LEVEL_COVERAGE, "coverage", "min", tol.level1),
        ObjectiveLevel(LEVEL_SOFT, "soft", "min", tol.level2),
        ObjectiveLevel(LEVEL_SATISFACTION, "satisfaction", "max", 0.0),
    ]


def add_satisfaction_terms(ctx: ModelContext) -> None:
    """Level 3 base term: sum_p pi_p sat^T_p (priority applies to time satisfaction, D6)."""
    for pid in professors(ctx):
        sat = time_satisfaction(ctx, pid)
        prof = ctx.instance.professor_by_id.get(pid)
        if sat is not None and prof is not None:
            ctx.add_objective_term(LEVEL_SATISFACTION, prof.priority * sat, f"sat_T[{pid}]")
