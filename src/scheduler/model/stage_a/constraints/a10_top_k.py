"""A10 — Top-k course preference."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import outside_top_k
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars


@constraint("A10")
class TopK:
    """Hard: no n_{p,c,k} exists for (p, c, k) outside the top K -- enforced when variables
    are created (filter, never big-M). Soft: each section taught outside the top K is a
    penalized slack: e_{p,c,k} >= n_{p,c,k}.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        if settings.mode is not Mode.SOFT:
            return
        for (p, c, k), n in n_vars(ctx).items():
            reason = outside_top_k(ctx.instance, ctx.config, p, c, k)
            if reason is None:
                continue
            e = ctx.add_slack(
                "A10",
                (p, c, k),
                [p, c, k.value],
                f"{p} teaches {c} {k.value}: {reason}",
                settings.weight,
                settings.level,
            )
            ctx.add_constraint(e >= n, "A10", [p, c, k.value])
