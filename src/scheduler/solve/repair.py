"""L5 — repair mode: stay close to a previous solution after the instance changed.

An extra objective level is inserted right after coverage: minimize the number of changed
decisions.
  Stage A: changes in z  ->  sum_{z_old=1} (1 - z_{p,c}) + sum_{z_old=0} z_{p,c}
  Stage B: sum_{(s,t,r) in old} (1 - y_{s,t,r})   (old triples no longer in F count as 1)
"""

from __future__ import annotations

from scheduler.config import Stage
from scheduler.domain import Solution
from scheduler.model.context import LEVEL_COVERAGE, LEVEL_REPAIR, ModelContext, ObjectiveLevel


def add_repair_level(ctx: ModelContext, previous: Solution) -> int:
    """Insert the repair level after coverage; return the number of forced changes
    (old decisions that no longer exist in the model)."""
    position = next(i for i, lv in enumerate(ctx.levels) if lv.key == LEVEL_COVERAGE) + 1
    ctx.levels.insert(position, ObjectiveLevel(LEVEL_REPAIR, "repair", "min", 0.0))
    if ctx.stage is Stage.A:
        return _stage_a(ctx, previous)
    return _stage_b(ctx, previous)


def _stage_a(ctx: ModelContext, previous: Solution) -> int:
    old = {(a.professor_id, a.course_id) for a in previous.assignments}
    z = ctx.family("z")
    terms = [
        (1 - var) if key in old else var
        for key, var in sorted(z.items(), key=lambda kv: str(kv[0]))
    ]
    forced = sum(1 for key in old if key not in z)
    ctx.add_objective_term(LEVEL_REPAIR, ctx.sum(terms) + forced, "repair (z changes)")
    return forced


def _stage_b(ctx: ModelContext, previous: Solution) -> int:
    y = ctx.family("y")
    terms = []
    forced = 0
    for p in sorted(previous.placements or (), key=lambda p: (p.course_id, p.section_label)):
        key = (p.section_key, p.pattern_id, p.room_id)
        if key in y:
            terms.append(1 - y[key])
        else:
            forced += 1
    ctx.add_objective_term(LEVEL_REPAIR, ctx.sum(terms) + forced, "repair (moved sections)")
    return forced
