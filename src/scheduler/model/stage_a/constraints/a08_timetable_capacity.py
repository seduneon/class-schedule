"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from typing import Any

from scheduler.config import ConstraintSettings, Mode
from scheduler.derived import (
    family_patterns,
    family_room_pattern_sets,
    hard_group_families,
    offering_rooms,
    pinned_family,
    room_set_label,
)
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars, sections_expr, z_vars
from scheduler.time.independent_set import alpha, alpha_of


@constraint("A8")
class TimetableCapacity:
    """sum_{c,k} n_{p,c,k} <= alpha_p, alpha_p = maximum number of pairwise non-overlapping
    time patterns available to p (independent-set MIP on the overlap graph, cached).

    With B13 hard (SPEC D11), alpha_p respects Phi_p and chi_p, and for each family f with
    professors pinned to it (P_f) and each room set R* = R(c,k):
    sum_{p in P_f} sum_{(c,k): R(c,k) subset of R*} n_{p,c,k} <= kappa_f(R*), and per hard
    conflict group g: m_{g,c,f} >= sum_k n_{p,c,k} (p in P_f), sum_{c in g} m_{g,c,f} <= alpha(U^f).
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        teaching = sorted({p for (p, _c, _k) in n_vars(ctx)})
        for p in teaching:
            a = alpha(ctx.instance, ctx.config, p)
            upper = sum(
                ctx.instance.offering_info[(c, k)].num_sections
                for (pp, c, k) in n_vars(ctx)
                if pp == p
            )
            if upper <= a:
                continue  # cannot bind
            rhs = a + self._slack(
                ctx, settings, p, [p], f"{p}: more sections than non-overlapping time patterns"
            )
            ctx.add_constraint(sections_expr(ctx, p) <= rhs, "A8", [p])
        self._family_rooms(ctx, settings, teaching)
        self._family_groups(ctx, settings, teaching)

    @staticmethod
    def _slack(
        ctx: ModelContext,
        settings: ConstraintSettings,
        key: object,
        entities: list[str],
        description: str,
    ) -> Any:
        if settings.mode is not Mode.SOFT:
            return 0
        return ctx.add_slack("A8", key, entities, description, settings.weight, settings.level)

    def _family_rooms(
        self, ctx: ModelContext, settings: ConstraintSettings, teaching: list[str]
    ) -> None:
        inst, cfg = ctx.instance, ctx.config
        buf = cfg.time.buffer_minutes
        pinned: dict[str, list[str]] = {}
        for p in teaching:
            if (f := pinned_family(inst, cfg, p)) is not None:
                pinned.setdefault(f, []).append(p)
        for f, profs in sorted(pinned.items()):
            keys = [(p, c, k) for (p, c, k) in n_vars(ctx) if p in profs]
            fits = {key: offering_rooms(inst, key[1:]) for key in keys}
            for i, rooms in enumerate(sorted({r for r in fits.values() if r}, key=sorted)):
                inside = [key for key in keys if fits[key] and fits[key] <= rooms]
                sets = family_room_pattern_sets(inst, cfg, f, rooms)
                kappa = sum(alpha_of(inst, s, buf) for s in sets)
                if sum(inst.offering_info[key[1:]].num_sections for key in inside) <= kappa:
                    continue  # cannot bind
                rhs = kappa + self._slack(
                    ctx,
                    settings,
                    ("rooms", f, i),
                    [f, str(i)],
                    f"{f}-only professors: more sections than {f} slots in {room_set_label(rooms)}",
                )
                n = n_vars(ctx)
                ctx.add_constraint(ctx.sum(n[key] for key in inside) <= rhs, "A8_rooms", [f, i])

    def _family_groups(
        self, ctx: ModelContext, settings: ConstraintSettings, teaching: list[str]
    ) -> None:
        inst, cfg = ctx.instance, ctx.config
        z = z_vars(ctx)
        for g, f in hard_group_families(inst, cfg):
            slots = alpha_of(inst, family_patterns(inst, cfg, f), cfg.time.buffer_minutes)
            pairs = [
                (p, c)
                for (p, c) in z
                if c in g.course_ids and p in teaching and pinned_family(inst, cfg, p) == f
            ]
            courses = sorted({c for _p, c in pairs})
            upper = sum(
                sum(i.num_sections for (cc, _k), i in inst.offering_info.items() if cc == c)
                for c in courses
            )
            if upper <= slots:
                continue  # cannot bind
            m = {c: ctx.add_var("m8", (g.id, c, f), [g.id, c, f], 0) for c in courses}
            for p, c in pairs:
                ctx.add_constraint(m[c] >= sections_expr(ctx, p, c), "A8_m", [g.id, c, f, p])
            rhs = slots + self._slack(
                ctx,
                settings,
                ("group", g.id, f),
                [g.id, f],
                f"{g.id}: {f}-only professors need more {f} time patterns than exist",
            )
            ctx.add_constraint(ctx.sum(m.values()) <= rhs, "A8_group", [g.id, f])
