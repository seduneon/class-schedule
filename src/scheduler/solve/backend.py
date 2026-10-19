"""Thin adapter over PuLP solvers (CBC, HiGHS): status mapping and statistics (SPEC §10)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pulp

from scheduler.config import SolverConfig

GAP_LIMIT = -7  # PuLP status code: stopped on the relative/absolute gap limit


class SolveStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"  # a solution exists but optimality is not proven (time limit)
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    NOT_SOLVED = "not_solved"

    @property
    def has_solution(self) -> bool:
        return self in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


@dataclass(frozen=True)
class SolveResult:
    """Outcome of one solver call."""

    status: SolveStatus
    objective: float | None
    best_bound: float | None
    wall_time_s: float
    nodes: int | None
    backend: str

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "objective": self.objective,
            "best_bound": self.best_bound,
            "wall_time_s": round(self.wall_time_s, 3),
            "nodes": self.nodes,
            "backend": self.backend,
        }


def make_solver(cfg: SolverConfig, time_limit_s: float | None = None) -> Any:
    """Configured PuLP solver; a fixed seed keeps runs reproducible."""
    limit = cfg.time_limit_s if time_limit_s is None else time_limit_s
    if cfg.backend == "highs":
        return pulp.HiGHS(
            msg=False,
            timeLimit=limit,
            threads=cfg.threads,
            gapRel=cfg.mip_gap,
            random_seed=cfg.seed,
        )
    return pulp.COIN_CMD(  # type: ignore[no-untyped-call]
        msg=False,
        timeLimit=limit,
        threads=cfg.threads,
        gapRel=cfg.mip_gap,
        randomSeed=cfg.seed,
        options=[f"randomCbcSeed {cfg.seed}"],
    )


def solve(prob: Any, cfg: SolverConfig, time_limit_s: float | None = None) -> SolveResult:
    """Solve ``prob`` and map PuLP's result to a :class:`SolveResult`."""
    started = time.perf_counter()
    stats = prob.solve(make_solver(cfg, time_limit_s))
    elapsed = time.perf_counter() - started
    status = _map_status(stats)
    objective = _finite(stats.objective) if status.has_solution else None
    if objective is None and status.has_solution:
        objective = _finite(pulp.value(prob.objective))
    return SolveResult(
        status=status,
        objective=objective,
        best_bound=_finite(stats.best_bound),
        wall_time_s=elapsed,
        nodes=stats.nodes if isinstance(stats.nodes, int) else None,
        backend=cfg.backend,
    )


def _map_status(stats: Any) -> SolveStatus:
    code = stats.status
    if code == 1 and stats.has_solution:
        return SolveStatus.OPTIMAL
    if code == GAP_LIMIT and stats.has_solution:
        # stopped because the gap reached ``mip_gap``: optimal within the configured gap
        return SolveStatus.OPTIMAL
    if code == -1:
        return SolveStatus.INFEASIBLE
    if code == -2:
        return SolveStatus.UNBOUNDED
    if stats.has_solution:  # e.g. -4 = time limit reached with an incumbent
        return SolveStatus.FEASIBLE
    if code == -3:
        # CBC reports some infeasible models as "Undefined"
        return SolveStatus.INFEASIBLE
    return SolveStatus.NOT_SOLVED


def _finite(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None
