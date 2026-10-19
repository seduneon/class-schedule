"""A1 — Section coverage."""

from __future__ import annotations

from scheduler.config import ConstraintSettings
from scheduler.derived import stage_a_offering_keys
from scheduler.model.context import LEVEL_COVERAGE, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars


@constraint("A1")
class Coverage:
    """sum_p n_{p,c,k} + a_{c,k} = N_{c,k} for all (c, k); a_{c,k} >= 0 minimized at level 1.

    The slack is always present, so the model stays feasible and reports what it could not cover.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        n = n_vars(ctx)
        for c, k in stage_a_offering_keys(ctx.instance, ctx.config):
            total = ctx.instance.offering_info[(c, k)].num_sections
            if total == 0:
                continue
            a = ctx.add_slack(
                "A1",
                (c, k),
                [c, k.value],
                f"{c} {k.value}: uncovered sections",
                weight=1.0,
                level=LEVEL_COVERAGE,
                up=total,
            )
            assigned = ctx.sum(v for (_p, cc, kk), v in n.items() if (cc, kk) == (c, k))
            ctx.add_constraint(assigned + a == total, "A1", [c, k.value])
