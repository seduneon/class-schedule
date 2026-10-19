"""B6 — Spread sections of a course."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import indexed, sections
from scheduler.time import cliques


@constraint("B6")
class SpreadSections:
    """For each (c, k) with >= 2 sections and each clique Q:
    sum_{s in (c,k)} sum_{t in Q} sum_r y_{s,t,r} <= 1 + o^6_{c,k,Q} (o only when soft)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        groups: dict[tuple[str, str], list[object]] = {}
        for sb in sections(ctx):
            groups.setdefault((sb.section.course_id, sb.section.section_type.value), []).append(
                sb.key
            )
        for (c, k), keys in sorted(groups.items()):
            if len(keys) < 2:
                continue
            for i, q in enumerate(cliques(ctx.instance, ctx.config.time.buffer_minutes)):
                ys = [v for key in keys for v in indexed(ctx, "section", key, q)]
                if len(ys) < 2:
                    continue
                rhs = 1
                if settings.mode is Mode.SOFT:
                    rhs = 1 + ctx.add_slack(
                        "B6",
                        (c, k, i),
                        [c, k, f"Q{i}"],
                        f"{c} {k}: sections overlap",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(ctx.sum(ys) <= rhs, "B6", [c, k, f"Q{i}"])
