"""A6 — Max distinct preparations."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import z_vars


@constraint("A6")
class MaxPreps:
    """sum_c z_{p,c} <= preps_p + v_p for professors with preps_p set (v_p only when soft)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        z = z_vars(ctx)
        for prof in ctx.instance.professors:
            if prof.max_preps is None:
                continue
            mine = [v for (p, _c), v in z.items() if p == prof.id]
            if len(mine) <= prof.max_preps:
                continue
            rhs = prof.max_preps
            if settings.mode is Mode.SOFT:
                rhs = prof.max_preps + ctx.add_slack(
                    "A6",
                    prof.id,
                    [prof.id],
                    f"{prof.id}: distinct courses above maximum",
                    settings.weight,
                    settings.level,
                )
            ctx.add_constraint(ctx.sum(mine) <= rhs, "A6", [prof.id])
