"""B1 — Section scheduled once."""

from __future__ import annotations

from scheduler.config import ConstraintSettings
from scheduler.model.context import LEVEL_COVERAGE, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import by_section, sections, y


@constraint("B1")
class ScheduledOnce:
    """sum_{t,r} y_{s,t,r} + b_s = 1 for every section s; b_s >= 0 minimized at level 1."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        grouped = by_section(ctx)
        for sb in sections(ctx):
            b = ctx.add_slack(
                "B1",
                sb.key,
                [sb.id],
                f"{sb.id} ({sb.professor_id}): unscheduled",
                weight=1.0,
                level=LEVEL_COVERAGE,
                up=1,
            )
            ctx.add_constraint(
                ctx.sum(y(ctx, tr) for tr in grouped[sb.key]) + b == 1, "B1", [sb.id]
            )
