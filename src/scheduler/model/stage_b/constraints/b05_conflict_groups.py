"""B5 — Conflict groups."""

from __future__ import annotations

from typing import Any

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import conflict_groups
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import indexed, sections
from scheduler.time import cliques


@constraint("B5")
class ConflictGroups:
    """For each group g, course c in g and clique Q:
        h_{c,Q} >= sum_{t in Q} sum_r y_{s,t,r}   for every section s of c,  h in {0,1}
        sum_{c in g} h_{c,Q} <= 1 + o_{g,Q}       (o only for soft groups)
    Sections of the same course may overlap. Only courses in some group get h variables.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        groups = conflict_groups(ctx.instance, ctx.config)
        if not groups:
            return
        grouped = sorted({c for g in groups for c in g.course_ids})
        secs_of: dict[str, list[Any]] = {}
        for sb in sections(ctx):
            secs_of.setdefault(sb.section.course_id, []).append(sb)
        for i, q in enumerate(cliques(ctx.instance, ctx.config.time.buffer_minutes)):
            h: dict[str, Any] = {}
            for c in grouped:
                per_section = [
                    (sb, indexed(ctx, "section", sb.key, q)) for sb in secs_of.get(c, [])
                ]
                per_section = [(sb, ys) for sb, ys in per_section if ys]
                if not per_section:
                    continue
                h[c] = ctx.add_var("h", (c, i), [c, f"Q{i}"], 0, 1, "Binary")
                for sb, ys in per_section:
                    ctx.add_constraint(h[c] >= ctx.sum(ys), "B5_h", [sb.id, f"Q{i}"])
            for g in groups:
                members = [h[c] for c in sorted(g.course_ids) if c in h]
                if len(members) < 2:
                    continue
                rhs: Any = 1
                if g.mode is Mode.SOFT:
                    rhs = 1 + ctx.add_slack(
                        "B5",
                        (g.id, i),
                        [g.id, f"Q{i}"],
                        f"conflict group {g.id}: courses overlap",
                        g.weight,
                        settings.level,
                    )
                ctx.add_constraint(ctx.sum(members) <= rhs, "B5", [g.id, f"Q{i}"])
