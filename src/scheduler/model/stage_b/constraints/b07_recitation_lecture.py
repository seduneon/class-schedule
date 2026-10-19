"""B7 — Recitation–lecture relation."""

from __future__ import annotations

from scheduler.config import B7Settings, ConstraintSettings, Mode
from scheduler.derived import linked_lectures
from scheduler.domain import SectionKey, SectionType
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import Triple, by_section, indexed, sections, y
from scheduler.time import cliques, earliest_meeting


@constraint("B7")
class RecitationLecture:
    """For a recitation s' and its linked lecture s (every lecture of c(s') if unlinked),
    for every clique Q: sum_{t in Q, r} (y_{s,t,r} + y_{s',t,r}) <= 1 + o^7 (o only when soft).
    With ``recitation_after_first_lecture``: for every lecture pattern t and recitation
    pattern t' whose earliest weekly meeting starts before t's, sum_r y_{s,t,r} + sum_r y_{s',t',r} <= 1
    (pairwise exclusion, always hard)."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        after = isinstance(settings, B7Settings) and settings.recitation_after_first_lecture
        present = {sb.key: sb for sb in sections(ctx)}
        grouped = by_section(ctx)
        all_cliques = cliques(ctx.instance, ctx.config.time.buffer_minutes)
        for rec in sections(ctx):
            if rec.section.section_type is not SectionType.R:
                continue
            for lec_section in linked_lectures(ctx.instance, rec.section):
                lec = present.get(lec_section.key)
                if lec is None:
                    continue
                for i, q in enumerate(all_cliques):
                    ys_l = indexed(ctx, "section", lec.key, q)
                    ys_r = indexed(ctx, "section", rec.key, q)
                    if not ys_l or not ys_r:
                        continue
                    rhs = 1
                    if settings.mode is Mode.SOFT:
                        rhs = 1 + ctx.add_slack(
                            "B7",
                            (rec.id, lec.id, i),
                            [rec.id, lec.id, f"Q{i}"],
                            f"recitation {rec.id} overlaps lecture {lec.id}",
                            settings.weight,
                            settings.level,
                        )
                    ctx.add_constraint(ctx.sum(ys_l + ys_r) <= rhs, "B7", [rec.id, lec.id, f"Q{i}"])
                if after:
                    self._order(ctx, grouped, rec.key, lec.key, rec.id, lec.id)

    @staticmethod
    def _order(
        ctx: ModelContext,
        grouped: dict[SectionKey, list[Triple]],
        rec_key: SectionKey,
        lec_key: SectionKey,
        rec_id: str,
        lec_id: str,
    ) -> None:
        pats = ctx.instance.pattern_by_id
        lec_pats = sorted({tr.pattern_id for tr in grouped[lec_key]})
        rec_pats = sorted({tr.pattern_id for tr in grouped[rec_key]})
        for t in lec_pats:
            for u in rec_pats:
                if earliest_meeting(pats[u]) < earliest_meeting(pats[t]):
                    lhs = ctx.sum(y(ctx, tr) for tr in grouped[lec_key] if tr.pattern_id == t)
                    lhs += ctx.sum(y(ctx, tr) for tr in grouped[rec_key] if tr.pattern_id == u)
                    ctx.add_constraint(lhs <= 1, "B7_order", [rec_id, lec_id, t, u])
