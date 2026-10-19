"""Lexicographic optimization (SPEC §5.3, §6.3).

Optimize level 1; add "level-1 expression within tolerance of its optimum"; continue
with level 2, and so on. No large penalty constants are ever mixed across levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pulp

from scheduler.config import SolverConfig
from scheduler.model.context import ModelContext, ObjectiveLevel
from scheduler.solve.backend import SolveResult, SolveStatus, solve

NUMERIC_EPS = 1e-6


@dataclass(frozen=True)
class LevelResult:
    level: ObjectiveLevel
    result: SolveResult | None  # None when the level had no variables
    value: float

    def as_dict(self) -> dict[str, object]:
        return {
            "level": self.level.key,
            "name": self.level.name,
            "sense": self.level.sense,
            "value": self.value,
            "solve": self.result.as_dict() if self.result else None,
        }


@dataclass
class LexResult:
    status: SolveStatus
    levels: list[LevelResult] = field(default_factory=list)

    def value(self, key: int) -> float:
        for lv in self.levels:
            if lv.level.key == key:
                return lv.value
        raise KeyError(key)

    @property
    def wall_time_s(self) -> float:
        return sum(lv.result.wall_time_s for lv in self.levels if lv.result)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "levels": [lv.as_dict() for lv in self.levels],
            "wall_time_s": round(self.wall_time_s, 3),
        }


def solve_lexicographic(ctx: ModelContext, cfg: SolverConfig) -> LexResult:
    """Solve ``ctx`` level by level; each optimum is locked in before the next level.

    For a min level with optimum v: add ``expr <= v + tol``; for a max level: ``expr >= v - tol``,
    where ``tol`` is the level's (absolute) tolerance plus a tiny numerical epsilon.
    The last level is not locked.
    If any level ends without a solution the result carries that status.
    """
    out = LexResult(SolveStatus.OPTIMAL)
    solved_once = False
    last = ctx.levels[-1].key
    for lv in ctx.levels:
        expr = ctx.level_expr(lv.key)
        if not _has_variables(expr) and solved_once:
            out.levels.append(LevelResult(lv, None, ctx.value(expr)))
            continue
        ctx.prob.setObjective(expr)
        ctx.prob.sense = pulp.LpMinimize if lv.sense == "min" else pulp.LpMaximize
        res = solve(ctx.prob, cfg)
        solved_once = True
        if not res.status.has_solution:
            out.status = res.status
            out.levels.append(LevelResult(lv, res, float("nan")))
            return out
        if res.status is SolveStatus.FEASIBLE:
            out.status = SolveStatus.FEASIBLE
        value = ctx.value(expr)
        out.levels.append(LevelResult(lv, res, value))
        if lv.key != last:  # the last level stays free (alternatives relax it to a gap)
            _lock(ctx, lv, expr, value)
    return out


def _lock(ctx: ModelContext, lv: ObjectiveLevel, expr: object, value: float) -> None:
    if not _has_variables(expr):
        return
    tol = lv.tolerance + NUMERIC_EPS * max(1.0, abs(value))
    if lv.sense == "min":
        ctx.add_constraint(expr <= value + tol, "lex", [lv.name])  # type: ignore[operator]
    else:
        ctx.add_constraint(expr >= value - tol, "lex", [lv.name])  # type: ignore[operator]


def _has_variables(expr: object) -> bool:
    return bool(getattr(expr, "keys", lambda: [])())
