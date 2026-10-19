"""B8 — Max teaching days."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import professors, sections, triples, y


@constraint("B8")
class MaxTeachingDays:
    """day_{p,d} >= sum_r y_{s,t,r} for every s in S_p and t meeting on d (day binary);
    sum_d day_{p,d} <= days_p + v^8_p (v only when soft)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        pats = ctx.instance.pattern_by_id
        for pid in professors(ctx):
            prof = ctx.instance.professor_by_id.get(pid)
            if prof is None or prof.max_days is None:
                continue
            mine = [tr for tr in triples(ctx) if tr.section.professor_id == pid]
            days = sorted({d for tr in mine for d in pats[tr.pattern_id].days})
            if len(days) <= prof.max_days:
                continue
            day = {d: ctx.add_var("day", (pid, d), [pid, d], 0, 1, "Binary") for d in days}
            own_sections = [s.key for s in sections(ctx) if s.professor_id == pid]
            for key in own_sections:
                for t in sorted({tr.pattern_id for tr in mine if tr.section.key == key}):
                    load = ctx.sum(
                        y(ctx, tr) for tr in mine if tr.section.key == key and tr.pattern_id == t
                    )
                    for d in pats[t].days:
                        ctx.add_constraint(day[d] >= load, "B8_day", [pid, d, key[0], key[2], t])
            rhs = prof.max_days
            if settings.mode is Mode.SOFT:
                rhs = prof.max_days + ctx.add_slack(
                    "B8",
                    pid,
                    [pid],
                    f"{pid}: teaching days above maximum",
                    settings.weight,
                    settings.level,
                )
            ctx.add_constraint(ctx.sum(day.values()) <= rhs, "B8", [pid])
