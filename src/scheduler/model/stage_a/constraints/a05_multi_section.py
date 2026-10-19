"""A5 — Multi-section preference."""

from __future__ import annotations

from scheduler.config import A5Settings, ConstraintSettings, Mode
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import sections_expr, z_vars


@constraint("A5")
class MultiSection:
    """mu_p = -1: sum_k n_{p,c,k} <= 1 + e_{p,c} (e penalized when soft, absent when hard).
    mu_p = +1: x_{p,c} <= sum_k n_{p,c,k} - z_{p,c}, x >= 0, rewarded with
    ``bonus_per_extra`` per section beyond the first at level 3."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        bonus = settings.bonus_per_extra if isinstance(settings, A5Settings) else 0.0
        for (p, c), z in z_vars(ctx).items():
            mu = ctx.instance.professor_by_id[p].multi_section_pref
            total = sections_expr(ctx, p, c)
            if mu == -1:
                rhs = 1
                if settings.mode is Mode.SOFT:
                    rhs = 1 + ctx.add_slack(
                        "A5",
                        (p, c),
                        [p, c],
                        f"{p}: more than one section of {c}",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(total <= rhs, "A5", [p, c])
            elif mu == 1 and bonus > 0:
                x = ctx.add_var("x_multi", (p, c), [p, c], 0, None)
                ctx.add_constraint(x <= total - z, "A5_bonus", [p, c])
                ctx.add_objective_term(LEVEL_SATISFACTION, bonus * x, f"A5 bonus[{p},{c}]")
