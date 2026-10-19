"""B10 — Max consecutive teaching."""

from __future__ import annotations

from scheduler.config import B10Settings, ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import busy, indexed, professors
from scheduler.time import consecutive_chains


@constraint("B10")
class MaxConsecutive:
    """For each window of k+1 consecutive adjacent patterns t_1 -> ... -> t_{k+1} on one day:
    sum_i busy_{p,t_i} <= k (+ slack when soft), k = ``max_consecutive``."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        k = settings.max_consecutive if isinstance(settings, B10Settings) else 3
        gap = ctx.config.time.adjacency_gap_minutes
        chains = ctx.instance.memo(
            ("chains", gap, k + 1), lambda: consecutive_chains(ctx.instance.patterns, gap, k + 1)
        )
        for pid in professors(ctx):
            for i, chain in enumerate(chains):
                if any(not indexed(ctx, "prof", pid, [t]) for t in chain):
                    continue
                rhs = k
                if settings.mode is Mode.SOFT:
                    rhs = k + ctx.add_slack(
                        "B10",
                        (pid, i),
                        [pid, *chain],
                        f"{pid}: more than {k} back-to-back",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(busy(ctx, pid, chain) <= rhs, "B10", [pid, i])
