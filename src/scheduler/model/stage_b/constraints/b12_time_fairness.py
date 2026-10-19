"""B12 — Time satisfaction fairness."""

from __future__ import annotations

from scheduler.config import ConstraintSettings
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import professors, time_satisfaction


@constraint("B12")
class TimeFairness:
    """m^T <= sat^T_p for every professor with sections; reward lambda^T m^T at level 3.
    sat^T_p = (1 / |S_p|) sum_{s in S_p} sum_{t,r} w^T_{p,t} y_{s,t,r}."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        lam = ctx.config.objective.lambda_time_fairness
        sats = [(pid, time_satisfaction(ctx, pid)) for pid in professors(ctx)]
        sats = [(pid, s) for pid, s in sats if s is not None]
        if not sats or lam == 0:
            return
        m = ctx.add_var("m_T", "m", ["min"], 0, 1)
        for pid, sat in sats:
            ctx.add_constraint(m <= sat, "B12", [pid])
        ctx.add_objective_term(LEVEL_SATISFACTION, lam * m, "B12 fairness")
