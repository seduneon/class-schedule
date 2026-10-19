"""L7 — integrated single-stage model (experiments only).

Variables v_{p,s,t,r} in {0,1} for p eligible for c(s) (A3) and available at t (B4),
(s, t, r) feasible for rooms and patterns. Must-rules only:
  coverage:  sum_{p,t,r} v_{p,s,t,r} + b_s = 1                       (A1 + B1, level 1)
  load:      L_min_p - d_p <= sum u_s v <= L_max_p                     (A2, d at level 2)
  pre:       sum_{s in (c,k), t, r} v_{p,s,t,r} >= pre_{p,c,k}         (A4)
  rooms:     sum_{p,s} sum_{t in Q} v <= 1 per room r, clique Q         (B2)
  professor: sum_{s} sum_{t in Q, r} v <= 1 per professor p, clique Q   (B3)
  groups:    h_{c,Q} >= sum_{p,t in Q,r} v for s in c; sum_{c in g} h_{c,Q} <= 1   (B5, hard)
Level 3 maximizes the linear proxy sum_p pi_p (sat^C_p + satT'_p) with
  satT'_p = (1 / L_max_p) sum u_s w^T_{p,t} v   (|S_p| is a variable here, so the Stage B
  normalization 1/|S_p| would be non-linear; :func:`proxy_objective` evaluates any solution
  with the same expression so both approaches are compared on equal terms).
"""

from __future__ import annotations

from typing import Any

from scheduler.config import Config, Stage
from scheduler.derived import (
    conflict_groups,
    is_eligible,
    pattern_blocked,
    pattern_problem,
    professor_unavailable,
    room_problem,
    room_unavailable,
)
from scheduler.domain import Assignment, Instance, Placement, Solution, Source
from scheduler.model.context import (
    LEVEL_COVERAGE,
    LEVEL_SATISFACTION,
    LEVEL_SOFT,
    ModelContext,
    ObjectiveLevel,
)
from scheduler.preferences import course_weights, time_weights
from scheduler.time import cliques

VKey = tuple[str, tuple[Any, ...], str, str]  # (professor, section key, pattern, room)


def build_integrated(instance: Instance, config: Config) -> ModelContext:
    tol = config.objective.tolerances
    ctx = ModelContext(
        "integrated",
        instance,
        config,
        Stage.B,
        [
            ObjectiveLevel(LEVEL_COVERAGE, "coverage", "min", tol.level1),
            ObjectiveLevel(LEVEL_SOFT, "soft", "min", tol.level2),
            ObjectiveLevel(LEVEL_SATISFACTION, "satisfaction", "max", 0.0),
        ],
    )
    wc = course_weights(instance, config.preferences)
    wt = time_weights(instance, config.preferences)
    v: dict[VKey, Any] = {}
    for s in instance.sections:
        rooms = [r for r in instance.rooms if room_problem(s, r) is None]
        pats = [
            t
            for t in instance.patterns
            if pattern_problem(instance, config, s, t) is None
            and not pattern_blocked(instance, t.id)
        ]
        for p in instance.professor_ids:
            if not is_eligible(instance, config, p, s.course_id, s.section_type):
                continue
            for t in pats:
                if professor_unavailable(instance, p, t.id):
                    continue
                for r in rooms:
                    if room_unavailable(instance, r.id, t.id):
                        continue
                    key = (p, s.key, t.id, r.id)
                    v[key] = ctx.add_var("v", key, [p, s.id, t.id, r.id], 0, 1, "Binary")
    sec_of = {s.key: s for s in instance.sections}

    for s in instance.sections:
        b = ctx.add_slack("A1", s.key, [s.id], f"{s.id}: not taught", 1.0, LEVEL_COVERAGE, up=1)
        ctx.add_constraint(
            ctx.sum(x for k, x in v.items() if k[1] == s.key) + b == 1, "cover", [s.id]
        )

    a2 = config.settings("A2")
    for prof in instance.professors:
        load = ctx.sum(sec_of[k[1]].units * x for k, x in v.items() if k[0] == prof.id)
        ctx.add_constraint(load <= prof.load_max, "A2_max", [prof.id])
        if prof.load_min > 0 and config.enabled("A2"):
            d = ctx.add_slack(
                "A2", prof.id, [prof.id], f"{prof.id}: underload", a2.weight, LEVEL_SOFT
            )
            ctx.add_constraint(load + d >= prof.load_min, "A2_min", [prof.id])
        lmax = prof.load_max
        if lmax > 0:
            sat = ctx.sum(
                prof.priority
                * sec_of[k[1]].units
                * (wc.get((prof.id, k[1][0], k[1][1]), 0.0) + wt.get((prof.id, k[2]), 0.0))
                / lmax
                * x
                for k, x in v.items()
                if k[0] == prof.id
            )
            ctx.add_objective_term(LEVEL_SATISFACTION, sat, f"sat[{prof.id}]")

    for (p, c, k), need in sorted(instance.pre_assigned.items(), key=lambda kv: str(kv[0])):
        ctx.add_constraint(
            ctx.sum(x for key, x in v.items() if key[0] == p and key[1][:2] == (c, k)) >= need,
            "A4",
            [p, c, k.value],
        )

    all_cliques = cliques(instance, config.time.buffer_minutes)
    for i, q in enumerate(all_cliques):
        for rid in instance.room_ids:
            terms = [x for key, x in v.items() if key[3] == rid and key[2] in q]
            if len(terms) > 1:
                ctx.add_constraint(ctx.sum(terms) <= 1, "B2", [rid, f"Q{i}"])
        for p in instance.professor_ids:
            terms = [x for key, x in v.items() if key[0] == p and key[2] in q]
            if len(terms) > 1:
                ctx.add_constraint(ctx.sum(terms) <= 1, "B3", [p, f"Q{i}"])
        for g in conflict_groups(instance, config):
            hs = []
            for c in sorted(g.course_ids):
                per_sec: dict[tuple[Any, ...], list[Any]] = {}
                for key, x in v.items():
                    if key[1][0] == c and key[2] in q:
                        per_sec.setdefault(key[1], []).append(x)
                if not per_sec:
                    continue
                h = ctx.get("h", (g.id, c, i)) or ctx.add_var(
                    "h", (g.id, c, i), [g.id, c, f"Q{i}"], 0, 1, "Binary"
                )
                for skey, xs in sorted(per_sec.items(), key=lambda kv: str(kv[0])):
                    ctx.add_constraint(h >= ctx.sum(xs), "B5_h", [g.id, c, skey[2], f"Q{i}"])
                hs.append(h)
            if len(hs) > 1:
                ctx.add_constraint(ctx.sum(hs) <= 1, "B5", [g.id, f"Q{i}"])
    ctx.data["v"] = v
    return ctx


def extract_integrated(ctx: ModelContext) -> Solution:
    v: dict[VKey, Any] = ctx.data["v"]
    sec_of = {s.key: s for s in ctx.instance.sections}
    assignments, placements = [], []
    for (p, skey, t, r), x in v.items():
        if ctx.value(x) > 0.5:
            s = sec_of[skey]
            assignments.append(
                Assignment(
                    p, s.course_id, s.section_type, s.label, s.capacity, s.units, Source.MODEL
                )
            )
            placements.append(Placement(s.course_id, s.section_type, s.label, t, r))
    return Solution(tuple(assignments), tuple(placements))


def proxy_objective(instance: Instance, solution: Solution, config: Config) -> float:
    """sum_p pi_p (sat^C_p + satT'_p) for any solution (the integrated level-3 expression)."""
    wc = course_weights(instance, config.preferences)
    wt = time_weights(instance, config.preferences)
    pattern_of = {p.section_key: p.pattern_id for p in solution.placements or ()}
    total = 0.0
    for a in solution.assignments:
        prof = instance.professor_by_id.get(a.professor_id)
        if prof is None or prof.load_max <= 0 or a.section_key not in pattern_of:
            continue
        w = wc.get((prof.id, a.course_id, a.section_type), 0.0) + wt.get(
            (prof.id, pattern_of[a.section_key]), 0.0
        )
        total += prof.priority * a.units * w / prof.load_max
    return total
