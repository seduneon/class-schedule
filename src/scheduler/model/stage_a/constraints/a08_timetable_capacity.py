"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars, sections_expr
from scheduler.time.independent_set import alpha


@constraint("A8")
class TimetableCapacity:
    """sum_{c,k} n_{p,c,k} <= alpha_p, alpha_p = maximum number of pairwise non-overlapping
    time patterns available to p (independent-set MIP on the overlap graph, cached)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        cfg = ctx.config
        teaching = sorted({p for (p, _c, _k) in n_vars(ctx)})
        for p in teaching:
            a = alpha(ctx.instance, p, cfg.time.days, cfg.time.buffer_minutes)
            upper = sum(
                ctx.instance.offering_info[(c, k)].num_sections
                for (pp, c, k) in n_vars(ctx)
                if pp == p
            )
            if upper <= a:
                continue  # cannot bind
            rhs = a
            if settings.mode is Mode.SOFT:
                rhs = a + ctx.add_slack(
                    "A8",
                    p,
                    [p],
                    f"{p}: more sections than non-overlapping time patterns",
                    settings.weight,
                    settings.level,
                )
            ctx.add_constraint(sections_expr(ctx, p) <= rhs, "A8", [p])
