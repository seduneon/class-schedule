"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.time import max_independent_set_size, professor_patterns
from scheduler.validation.core import Violation, check, severity_for


@check("A8")
def check_a8(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_{c,k} n_{p,c,k} <= alpha_p, alpha_p = max number of pairwise non-overlapping patterns
    available to p (computed here without a solver)."""
    counts = Counter(a.professor_id for a in solution.assignments)
    out = []
    for pid, n in sorted(counts.items()):
        if pid not in instance.professor_by_id:
            continue
        pats = professor_patterns(instance, pid, config.time.days)
        alpha = max_independent_set_size(pats, config.time.buffer_minutes)
        if n > alpha:
            out.append(
                Violation(
                    "A8",
                    severity_for(settings),
                    f"{pid} has {n} sections but only {alpha} non-overlapping available time patterns",
                    (pid,),
                    size=n - alpha,
                )
            )
    return out
