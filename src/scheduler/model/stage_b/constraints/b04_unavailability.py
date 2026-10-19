"""B4 — Unavailability and blocked slots."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import by_section, sections, y


@constraint("B4")
class Unavailability:
    """Hard: enforced through F (variables for blocked or unavailable patterns never exist).
    Soft: unavailable patterns stay in F and u_s >= sum of y_{s,t,r} over unavailable t is
    penalized at the configured level ("strongly disliked"). Blocked slots stay filtered.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        if settings.mode is not Mode.SOFT:
            return
        grouped = by_section(ctx)
        for sb in sections(ctx):
            bad = [y(ctx, tr) for tr in grouped[sb.key] if tr.unavailable]
            if not bad:
                continue
            u = ctx.add_slack(
                "B4",
                sb.key,
                [sb.id],
                f"{sb.id}: scheduled while {sb.professor_id} is unavailable",
                settings.weight,
                settings.level,
            )
            ctx.add_constraint(u >= ctx.sum(bad), "B4", [sb.id])
