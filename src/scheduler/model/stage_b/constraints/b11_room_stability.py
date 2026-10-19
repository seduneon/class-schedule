"""B11 — Room stability."""

from __future__ import annotations

from typing import Any

from scheduler.config import B11Settings, ConstraintSettings
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import professors, triples, y


@constraint("B11")
class RoomStability:
    """gamma_{p,r} >= y_{s,t,r} for every s in S_p; subtract ``weight`` * sum_r gamma_{p,r}
    (rooms used per professor) at level 3. ``scope: building`` uses gamma_{p,b} instead."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        building = isinstance(settings, B11Settings) and settings.scope == "building"
        rooms = ctx.instance.room_by_id
        own = set(professors(ctx))
        gamma: dict[tuple[str, str], Any] = {}
        for tr in triples(ctx):
            pid = tr.section.professor_id
            if pid not in own:
                continue
            place = rooms[tr.room_id].building if building else tr.room_id
            key = (pid, place)
            if key not in gamma:
                gamma[key] = ctx.add_var("gamma", key, [pid, place], 0, 1)
            ctx.add_constraint(
                gamma[key] >= y(ctx, tr), "B11", [pid, tr.section.id, tr.pattern_id, tr.room_id]
            )
        if gamma and settings.weight > 0:
            ctx.add_objective_term(
                LEVEL_SATISFACTION, -settings.weight * ctx.sum(gamma.values()), "B11 rooms used"
            )
