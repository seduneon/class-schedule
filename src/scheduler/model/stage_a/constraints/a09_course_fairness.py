"""A9 — Course satisfaction fairness."""

from __future__ import annotations

from scheduler.config import ConstraintSettings
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import course_satisfaction


@constraint("A9")
class CourseFairness:
    """m^C <= sat^C_p for every professor with load_min_p > 0; reward lambda^C m^C at level 3.
    sat^C_p = (1 / L_max_p) sum_{c,k} u_{c,k} w^C_{p,c} n_{p,c,k}."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        lam = ctx.config.objective.lambda_course_fairness
        profs = [p for p in ctx.instance.professors if p.load_min > 0]
        sats = [(p.id, course_satisfaction(ctx, p.id)) for p in profs]
        sats = [(pid, s) for pid, s in sats if s is not None]
        if not sats or lam == 0:
            return
        m = ctx.add_var("m_C", "m", ["min"], 0, 1)
        for pid, sat in sats:
            ctx.add_constraint(m <= sat, "A9", [pid])
        ctx.add_objective_term(LEVEL_SATISFACTION, lam * m, "A9 fairness")
