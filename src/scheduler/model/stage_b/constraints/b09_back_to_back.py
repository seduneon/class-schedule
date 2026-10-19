"""B9 — Back-to-back preference."""

from __future__ import annotations

from scheduler.config import B9Settings, ConstraintSettings, Mode
from scheduler.domain import ScheduleStyle
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import busy, indexed, professors
from scheduler.time import adjacency


@constraint("B9")
class BackToBack:
    """For each adjacent pair (t, t'):
    compact: beta_{p,t,t'} <= busy_{p,t}, beta <= busy_{p,t'}, beta in [0, 1], rewarded
             (``reward`` per pair) at level 3;
    spread:  busy_{p,t} + busy_{p,t'} <= 1 + o^9_{p,t,t'} (o only when soft)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        reward = settings.reward if isinstance(settings, B9Settings) else 0.0
        pairs = sorted(
            {
                (p.first, p.second)
                for p in adjacency(ctx.instance, ctx.config.time.adjacency_gap_minutes)
            }
        )
        for pid in professors(ctx):
            prof = ctx.instance.professor_by_id.get(pid)
            style = prof.schedule_style if prof else ScheduleStyle.NONE
            if style is ScheduleStyle.NONE:
                continue
            for t, u in pairs:
                if not indexed(ctx, "prof", pid, [t]) or not indexed(ctx, "prof", pid, [u]):
                    continue
                bt, bu = busy(ctx, pid, [t]), busy(ctx, pid, [u])
                if style is ScheduleStyle.COMPACT and reward > 0:
                    beta = ctx.add_var("beta", (pid, t, u), [pid, t, u], 0, 1)
                    ctx.add_constraint(beta <= bt, "B9_beta_t", [pid, t, u])
                    ctx.add_constraint(beta <= bu, "B9_beta_u", [pid, t, u])
                    ctx.add_objective_term(LEVEL_SATISFACTION, reward * beta, f"B9 compact[{pid}]")
                elif style is ScheduleStyle.SPREAD:
                    rhs = 1
                    if settings.mode is Mode.SOFT:
                        rhs = 1 + ctx.add_slack(
                            "B9",
                            (pid, t, u),
                            [pid, t, u],
                            f"{pid}: back-to-back {t} -> {u}",
                            settings.weight,
                            settings.level,
                        )
                    ctx.add_constraint(bt + bu <= rhs, "B9", [pid, t, u])
