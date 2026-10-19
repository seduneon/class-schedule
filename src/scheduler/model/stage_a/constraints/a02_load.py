"""A2 — Teaching load range."""

from __future__ import annotations

from scheduler.config import A2Settings, ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import load_expr


@constraint("A2")
class LoadRange:
    """L_min_p - d^-_p <= sum_{c,k} u_{c,k} n_{p,c,k} <= L_max_p + d^+_p for all p.

    Hard: d^+- = 0. Soft: d^- penalized (weight, level); d^+ penalized only when
    ``allow_overload``, otherwise the upper bound stays hard.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        allow_over = isinstance(settings, A2Settings) and settings.allow_overload
        soft = settings.mode is Mode.SOFT
        for prof in ctx.instance.professors:
            load = load_expr(ctx, prof.id)
            lower = load
            if soft and prof.load_min > 0:
                lower = load + ctx.add_slack(
                    "A2",
                    ("under", prof.id),
                    ["under", prof.id],
                    f"{prof.id}: units below minimum load",
                    settings.weight,
                    settings.level,
                )
            if prof.load_min > 0:
                ctx.add_constraint(lower >= prof.load_min, "A2_min", [prof.id])
            upper = load
            if soft and allow_over:
                upper = load - ctx.add_slack(
                    "A2",
                    ("over", prof.id),
                    ["over", prof.id],
                    f"{prof.id}: units above maximum load",
                    settings.weight,
                    settings.level,
                )
            ctx.add_constraint(upper <= prof.load_max, "A2_max", [prof.id])
