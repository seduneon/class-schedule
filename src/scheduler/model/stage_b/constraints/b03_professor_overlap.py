"""B3 — No professor overlap."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import indexed, professors
from scheduler.time import cliques


@constraint("B3")
class NoProfessorOverlap:
    """sum_{t in Q} busy_{p,t} <= 1 for every professor p and clique Q.
    Placeholder instructors (TBA-*) are exempt."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        for p in professors(ctx):
            for i, q in enumerate(cliques(ctx.instance, ctx.config.time.buffer_minutes)):
                ys = indexed(ctx, "prof", p, q)
                if len(ys) < 2:
                    continue
                rhs = 1
                if settings.mode is Mode.SOFT:
                    rhs = 1 + ctx.add_slack(
                        "B3",
                        (p, i),
                        [p, f"Q{i}"],
                        f"{p} double-booked",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(ctx.sum(ys) <= rhs, "B3", [p, f"Q{i}"])
