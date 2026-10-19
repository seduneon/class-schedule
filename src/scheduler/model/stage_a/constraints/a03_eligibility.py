"""A3 — Eligibility."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import is_eligible
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars


@constraint("A3")
class Eligibility:
    """Hard: no n_{p,c,k} exists for ineligible (p, c, k) -- enforced when variables are
    created (filter, never big-M). Soft: variables exist and each section an ineligible
    professor teaches is a penalized slack: e_{p,c,k} >= n_{p,c,k}.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        if settings.mode is not Mode.SOFT:
            return
        hard_cfg = ctx.config.with_mode("A3", Mode.HARD)
        for (p, c, k), n in n_vars(ctx).items():
            if is_eligible(ctx.instance, hard_cfg, p, c, k):
                continue
            e = ctx.add_slack(
                "A3",
                (p, c, k),
                [p, c, k.value],
                f"{p} teaches {c} {k.value} although ineligible",
                settings.weight,
                settings.level,
            )
            ctx.add_constraint(e >= n, "A3", [p, c, k.value])
