"""A7 — Lecture–recitation staffing."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import courses_with_lectures_and_recitations
from scheduler.domain import SectionType
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars

L, R = SectionType.L, SectionType.R


@constraint("A7")
class RecitationStaffing:
    """``faculty``: recitations are assigned like lectures (no extra rows).
    ``external``: recitations are excluded from Stage A when variables are created and go
    to Stage B with placeholder ``TBA-<course>``.
    ``same_as_lecture``: per course with lectures and recitations, integer share band
        N_L n_{p,c,R} >= N_R n_{p,c,L} - (N_L - 1)
        N_L n_{p,c,R} <= N_R n_{p,c,L} + (N_L - 1)
    i.e. floor(N_R share) <= n_R <= ceil(N_R share) with share = n_{p,c,L} / N_L.
    Soft mode adds penalized slacks to both sides."""

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        if ctx.config.recitations.staffing != "same_as_lecture":
            return
        n = n_vars(ctx)
        soft = settings.mode is Mode.SOFT
        for c in courses_with_lectures_and_recitations(ctx.instance):
            n_l = ctx.instance.offering_info[(c, L)].num_sections
            n_r = ctx.instance.offering_info[(c, R)].num_sections
            for p in ctx.instance.professor_ids:
                lec, rec = n.get((p, c, L)), n.get((p, c, R))
                if lec is None and rec is None:
                    continue
                lec_expr = lec if lec is not None else 0
                rec_expr = rec if rec is not None else 0
                lo_slack = hi_slack = 0
                if soft:
                    lo_slack = ctx.add_slack(
                        "A7",
                        ("lo", p, c),
                        ["lo", p, c],
                        f"{p}: too few {c} recitations",
                        settings.weight,
                        settings.level,
                    )
                    hi_slack = ctx.add_slack(
                        "A7",
                        ("hi", p, c),
                        ["hi", p, c],
                        f"{p}: too many {c} recitations",
                        settings.weight,
                        settings.level,
                    )
                ctx.add_constraint(
                    n_l * rec_expr + lo_slack >= n_r * lec_expr - (n_l - 1), "A7_lo", [p, c]
                )
                ctx.add_constraint(
                    n_l * rec_expr - hi_slack <= n_r * lec_expr + (n_l - 1), "A7_hi", [p, c]
                )
