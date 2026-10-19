"""B13 — Day-family preference."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import family_mixing, off_family
from scheduler.domain import FamilyMixing
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_b.variables import Triple, professors, triples, y


@constraint("B13")
class DayFamily:
    """Off-family: sum_{s in S_p} sum_{t: f(t) not in Phi_p} sum_r y_{s,t,r} <= o^13_p
    (soft; in hard mode those triples are filtered out of F, so nothing is built here).
    Mixing (chi_p != allow): phi_{p,f} >= sum_{t: f(t)=f} sum_r y_{s,t,r} for every
    s in S_p, phi binary, sum_f phi_{p,f} <= 1 + q^13_p; q only for ``avoid`` in soft mode.
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        inst = ctx.instance
        for pid in professors(ctx):
            mine = [tr for tr in triples(ctx) if tr.section.professor_id == pid]
            bad = [y(ctx, tr) for tr in mine if off_family(inst, pid, tr.pattern_id)]
            if bad and settings.mode is Mode.SOFT:
                o = ctx.add_slack(
                    "B13",
                    (pid, "off"),
                    [pid, "off"],
                    f"{pid}: sections outside preferred day families",
                    settings.weight,
                    settings.level,
                )
                ctx.add_constraint(ctx.sum(bad) <= o, "B13_off", [pid])
            self._mixing(ctx, settings, pid, mine)

    @staticmethod
    def _mixing(
        ctx: ModelContext, settings: ConstraintSettings, pid: str, mine: list[Triple]
    ) -> None:
        mixing = family_mixing(ctx.instance, ctx.config, pid)
        pats = ctx.instance.pattern_by_id
        families = sorted({pats[tr.pattern_id].family for tr in mine})
        if mixing is FamilyMixing.ALLOW or len(families) <= 1:
            return
        phi = {f: ctx.add_var("phi", (pid, f), [pid, f], 0, 1, "Binary") for f in families}
        for key in sorted({tr.section.key for tr in mine}, key=str):
            for f in families:
                ys = [
                    y(ctx, tr)
                    for tr in mine
                    if tr.section.key == key and pats[tr.pattern_id].family == f
                ]
                if ys:
                    ctx.add_constraint(phi[f] >= ctx.sum(ys), "B13_phi", [pid, f, key[0], key[2]])
        rhs = 1
        if mixing is FamilyMixing.AVOID and settings.mode is Mode.SOFT:
            rhs = 1 + ctx.add_slack(
                "B13",
                (pid, "mix"),
                [pid, "mix"],
                f"{pid}: day families used beyond one",
                settings.weight,
                settings.level,
            )
        ctx.add_constraint(ctx.sum(phi.values()) <= rhs, "B13_mix", [pid])
