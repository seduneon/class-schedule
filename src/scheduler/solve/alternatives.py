"""L3 — alternative solutions via no-good cuts.

Stage A cuts on z:   sum_{z*=1} (1 - z) + sum_{z*=0} z >= d
Stage B cuts on y~_{s,t} = sum_r y_{s,t,r} (room changes do not count), same form.
Every alternative keeps the locked lexicographic levels (coverage and, when present, repair
and soft slacks) and keeps level 3 within ``optimality_gap`` of the best solution.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, cast

import pulp

from scheduler.config import Config, Stage
from scheduler.domain import Instance, Solution, label_sort_key
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.solve.backend import solve

EPS = 1e-6


@dataclass(frozen=True)
class Alternative:
    rank: int
    solution: Solution
    objective: float
    relative_gap: float
    diff: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "objective": self.objective,
            "relative_gap": self.relative_gap,
            "diff": list(self.diff),
        }


def decision_vector(ctx: ModelContext) -> dict[Hashable, Any]:
    """Binary decisions the cuts act on: z (Stage A) or y~_{s,t} expressions (Stage B)."""
    if ctx.stage is Stage.A:
        return dict(sorted(ctx.family("z").items(), key=lambda kv: str(kv[0])))
    grouped: dict[Hashable, list[Any]] = {}
    for key, var in ctx.family("y").items():
        skey, t, _r = cast(tuple[Any, str, str], key)
        grouped.setdefault((skey, t), []).append(var)
    return {k: pulp.lpSum(v) for k, v in sorted(grouped.items(), key=lambda kv: str(kv[0]))}


def add_no_good(ctx: ModelContext, values: dict[Hashable, float], d: int, index: int) -> None:
    """sum_{x*=1} (1 - x) + sum_{x*=0} x >= d over the decision vector."""
    vec = decision_vector(ctx)
    expr = pulp.lpSum((1 - vec[k]) if values.get(k, 0) > 0.5 else vec[k] for k in vec)
    ctx.add_constraint(expr >= d, "nogood", [index])


def current_values(ctx: ModelContext) -> dict[Hashable, float]:
    return {k: ctx.value(v) for k, v in decision_vector(ctx).items()}


def find_alternatives(
    ctx: ModelContext,
    best: Solution,
    best_objective: float,
    extract: Any,
    config: Config,
    count: int | None = None,
) -> list[Alternative]:
    """Up to ``count`` alternatives, each at Hamming distance >= ``min_difference`` from the
    best solution and from every earlier alternative. ``extract(ctx) -> Solution``."""
    alt_cfg = config.alternatives
    n = alt_cfg.count if count is None else count
    if n <= 0:
        return []
    level3 = ctx.level_expr(LEVEL_SATISFACTION)
    floor = best_objective - alt_cfg.optimality_gap * max(abs(best_objective), EPS)
    ctx.add_constraint(level3 >= floor - EPS, "alt_gap", [])
    ctx.prob.setObjective(level3)
    ctx.prob.sense = pulp.LpMaximize
    found: list[tuple[float, Solution]] = []
    add_no_good(ctx, _values_of(ctx, best), alt_cfg.min_difference, 0)
    for i in range(1, n + 1):
        res = solve(ctx.prob, config.solver)
        if not res.status.has_solution:
            break
        value = ctx.value(level3)
        found.append((value, extract(ctx)))
        add_no_good(ctx, current_values(ctx), alt_cfg.min_difference, i)
    found.sort(key=lambda item: -item[0])
    return [
        Alternative(
            rank=i + 1,
            solution=sol,
            objective=value,
            relative_gap=(best_objective - value) / max(abs(best_objective), EPS),
            diff=diff_solutions(ctx.instance, best, sol),
        )
        for i, (value, sol) in enumerate(found)
    ]


def _values_of(ctx: ModelContext, solution: Solution) -> dict[Hashable, float]:
    """Decision values of a given solution (not the current solver values)."""
    if ctx.stage is Stage.A:
        taught = {(a.professor_id, a.course_id) for a in solution.assignments}
        return {k: 1.0 if k in taught else 0.0 for k in ctx.family("z")}
    used = {(p.section_key, p.pattern_id) for p in solution.placements or ()}
    return {k: 1.0 if k in used else 0.0 for k in decision_vector(ctx)}


def diff_solutions(instance: Instance, base: Solution, other: Solution) -> tuple[str, ...]:
    """Human-readable differences of ``other`` against ``base``."""
    if base.placements is None or other.placements is None:
        old = Counter((a.professor_id, a.course_id, a.section_type.value) for a in base.assignments)
        new = Counter(
            (a.professor_id, a.course_id, a.section_type.value) for a in other.assignments
        )
        out = []
        for key in sorted(set(old) | set(new)):
            if old[key] != new[key]:
                p, c, k = key
                out.append(f"{p}: {c} {k} {old[key]} -> {new[key]}")
        return tuple(out)
    before = {p.section_key: p for p in base.placements}
    after = {p.section_key: p for p in other.placements}
    lines = []
    for key in sorted(set(before) | set(after), key=lambda k: (k[0], label_sort_key(k[2]))):
        b, a = before.get(key), after.get(key)
        sid = f"{key[0]}-{key[2]}"
        if b is None or a is None:
            lines.append(
                f"{sid}: {'unscheduled' if b is None else b.pattern_id} -> {'unscheduled' if a is None else a.pattern_id}"
            )
        elif b.pattern_id != a.pattern_id:
            lines.append(f"{sid}: {b.pattern_id} -> {a.pattern_id}")
        elif b.room_id != a.room_id:
            lines.append(f"{sid}: room {b.room_id} -> {a.room_id}")
    return tuple(lines)
