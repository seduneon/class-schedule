"""B12 — Time satisfaction fairness."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.metrics import professor_metrics
from scheduler.validation.core import Violation, check

EPS = 1e-9


@check("B12")
def check_b12(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """B12 is an objective term (reward lambda^T m^T with m^T <= sat^T_p). The check reports
    the unfair extreme: a professor with sections whose time satisfaction sat^T_p is 0.
    Always a warning."""
    return [
        Violation(
            "B12",
            "warning",
            f"{m.professor_id} got none of their preferred times (time satisfaction 0)",
            (m.professor_id,),
        )
        for m in professor_metrics(instance, solution, config)
        if m.sections and m.sat_time is not None and m.sat_time <= EPS
    ]
