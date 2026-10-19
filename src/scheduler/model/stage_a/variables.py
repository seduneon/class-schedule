"""Stage A variables (SPEC §5.1).

n_{p,c,k} in Z, 0 <= n <= N_{c,k}: created only for eligible (p, c, k) (A3 filter; a
pre-assignment or pin overrides). z_{p,c} in {0,1}, linked by
z_{p,c} <= sum_k n_{p,c,k} <= (sum_k N_{c,k}) z_{p,c}. Stage A pins (L4) fix n.
"""

from __future__ import annotations

from typing import Any, cast

from scheduler.config import Mode
from scheduler.derived import is_eligible, stage_a_offering_keys
from scheduler.domain import SectionType
from scheduler.model.context import ModelContext
from scheduler.preferences import course_weights

NKey = tuple[str, str, SectionType]


def build_variables(ctx: ModelContext) -> None:
    inst, cfg = ctx.instance, ctx.config
    soft_a3 = cfg.mode("A3") is Mode.SOFT
    keys = [k for k in stage_a_offering_keys(inst, cfg) if inst.offering_info[k].num_sections > 0]
    pins = inst.stage_a_pin_counts
    for p in inst.professor_ids:
        for c, k in keys:
            if not (soft_a3 or is_eligible(inst, cfg, p, c, k)) and (p, c, k) not in pins:
                continue
            n_max = inst.offering_info[(c, k)].num_sections
            var = ctx.add_var("n", (p, c, k), [p, c, k.value], 0, n_max, "Integer")
            if (p, c, k) in pins:
                ctx.fix(var, min(pins[(p, c, k)], n_max))
    by_course: dict[tuple[str, str], list[NKey]] = {}
    for p, c, k in n_vars(ctx):
        by_course.setdefault((p, c), []).append((p, c, k))
    n = n_vars(ctx)
    for (p, c), nkeys in sorted(by_course.items()):
        z = ctx.add_var("z", (p, c), [p, c], 0, 1, "Binary")
        total = ctx.sum(n[key] for key in nkeys)
        big = sum(inst.offering_info[(c, key[2])].num_sections for key in nkeys)
        ctx.add_constraint(z <= total, "link_z_lo", [p, c])
        ctx.add_constraint(total <= big * z, "link_z_hi", [p, c])
    ctx.data["course_weights"] = course_weights(inst, cfg.preferences)


def n_vars(ctx: ModelContext) -> dict[NKey, Any]:
    """n_{p,c,k} keyed by (p, c, k), in sorted key order."""
    fam = cast(dict[NKey, Any], ctx.family("n"))
    return {k: fam[k] for k in sorted(fam, key=lambda k: (k[0], k[1], k[2].value))}


def z_vars(ctx: ModelContext) -> dict[tuple[str, str], Any]:
    """z_{p,c} keyed by (p, c)."""
    fam = cast(dict[tuple[str, str], Any], ctx.family("z"))
    return {k: fam[k] for k in sorted(fam)}


def load_expr(ctx: ModelContext, professor_id: str) -> Any:
    """sum_{c,k} u_{c,k} n_{p,c,k}."""
    info = ctx.instance.offering_info
    return ctx.sum(
        info[(c, k)].units * v for (p, c, k), v in n_vars(ctx).items() if p == professor_id
    )


def sections_expr(ctx: ModelContext, professor_id: str, course_id: str | None = None) -> Any:
    """sum_k n_{p,c,k} for one course, or sum_{c,k} n_{p,c,k} if ``course_id`` is None."""
    return ctx.sum(
        v
        for (p, c, _k), v in n_vars(ctx).items()
        if p == professor_id and (course_id is None or c == course_id)
    )


def course_satisfaction(ctx: ModelContext, professor_id: str) -> Any | None:
    """sat^C_p = (1 / L_max_p) sum_{c,k} u_{c,k} w^C_{p,c,k} n_{p,c,k}; None if L_max_p = 0."""
    prof = ctx.instance.professor_by_id[professor_id]
    if prof.load_max <= 0:
        return None
    w: dict[tuple[str, str, SectionType], float] = ctx.data["course_weights"]
    info = ctx.instance.offering_info
    return ctx.sum(
        (info[(c, k)].units * w.get((p, c, k), 0.0) / prof.load_max) * v
        for (p, c, k), v in n_vars(ctx).items()
        if p == professor_id
    )
