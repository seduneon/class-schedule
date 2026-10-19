"""B2 — No room overlap."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import indexed
from scheduler.time import cliques


@constraint("B2")
class NoRoomOverlap:
    """sum_s sum_{t in Q} y_{s,t,r} <= 1 for every room r and maximal clique Q (soft: + slack)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        for r in ctx.instance.room_ids:
            for i, q in enumerate(cliques(ctx.instance, ctx.config.time.buffer_minutes)):
                ys = indexed(ctx, "room", r, q)
                if len(ys) < 2:
                    continue
                rhs = 1
                if settings.mode is Mode.SOFT:
                    rhs = 1 + ctx.add_slack(
                        "B2",
                        (r, i),
                        [r, f"Q{i}"],
                        f"room {r} double-booked",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(ctx.sum(ys) <= rhs, "B2", [r, f"Q{i}"])
